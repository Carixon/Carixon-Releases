"""Offline licensing logic for the JBS client."""
from __future__ import annotations

import json
import os
import platform
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from cryptography.hazmat.primitives.asymmetric import rsa

from jbs_common.crypto import extract_signed_document, load_public_key
from jbs_common.storage import decrypt_json_from_file_or_default, encrypt_json_to_file

from .hwid import compute_hwid

APP_STORAGE_SUBDIR = "JBS"
LICENSE_FILENAME = "license.jbslic"
ACTIVATIONS_FILENAME = "activations.dat"
STATE_FILENAME = "state.dat"
REQUEST_EXTENSION = ".jbsreq"
ACTIVATION_EXTENSION = ".jbsact"
DEACTIVATION_EXTENSION = ".jbsunreq"
DEACTIVATION_RESPONSE_EXTENSION = ".jbsunact"


@dataclass
class License:
    license_id: str
    plan: str
    issued_utc: datetime
    expires_utc: Optional[datetime]
    max_devices: int
    note: str = ""

    @property
    def is_lifetime(self) -> bool:
        return self.expires_utc is None

    @classmethod
    def from_payload(cls, payload: Dict[str, str]) -> "License":
        return cls(
            license_id=payload["license_id"],
            plan=payload["plan"],
            issued_utc=datetime.fromisoformat(payload["issued_utc"]),
            expires_utc=datetime.fromisoformat(payload["expires_utc"]) if payload.get("expires_utc") else None,
            max_devices=int(payload.get("max_devices", 2)),
            note=payload.get("note", ""),
        )


@dataclass
class ActivationRecord:
    hwid: str
    approved_at_utc: datetime
    device_index: int
    remark: str = ""

    @classmethod
    def from_payload(cls, payload: Dict[str, str]) -> "ActivationRecord":
        return cls(
            hwid=payload["approved_hwid"],
            approved_at_utc=datetime.fromisoformat(payload["approved_at_utc"]),
            device_index=int(payload.get("device_index", 1)),
            remark=payload.get("remark", ""),
        )


@dataclass
class ActivationState:
    license_id: str
    devices: List[ActivationRecord] = field(default_factory=list)

    def to_serializable(self) -> Dict[str, List[Dict[str, str]]]:
        return {
            "license_id": self.license_id,
            "devices": [
                {
                    "hwid": record.hwid,
                    "approved_at_utc": record.approved_at_utc.isoformat(),
                    "device_index": record.device_index,
                    "remark": record.remark,
                }
                for record in self.devices
            ],
        }

    @classmethod
    def from_serializable(cls, data: Dict[str, List[Dict[str, str]]]) -> "ActivationState":
        state = cls(license_id=data.get("license_id", ""))
        for payload in data.get("devices", []):
            state.devices.append(
                ActivationRecord(
                    hwid=payload["hwid"],
                    approved_at_utc=datetime.fromisoformat(payload["approved_at_utc"]),
                    device_index=int(payload.get("device_index", 1)),
                    remark=payload.get("remark", ""),
                )
            )
        return state

    def get_record_for_hwid(self, hwid: str) -> Optional[ActivationRecord]:
        for record in self.devices:
            if record.hwid == hwid:
                return record
        return None

    def upsert_record(self, record: ActivationRecord) -> None:
        existing = self.get_record_for_hwid(record.hwid)
        if existing:
            existing.approved_at_utc = record.approved_at_utc
            existing.device_index = record.device_index
            existing.remark = record.remark
        else:
            self.devices.append(record)

    def remove_record(self, hwid: str) -> None:
        self.devices = [record for record in self.devices if record.hwid != hwid]


class TimeRollbackDetected(Exception):
    """Raised when the wall clock moved backwards."""


class LicenseManager:
    def __init__(self, public_key_pem: bytes, base_path: Optional[Path] = None) -> None:
        self.public_key: rsa.RSAPublicKey = load_public_key(public_key_pem)
        self.base_path = base_path or self._default_storage_path()
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.license_path = self._discover_license_path()
        self.license: Optional[License] = None
        self.activation_state = ActivationState(license_id="")
        self.state_data: Dict[str, str] = {}
        self.current_hwid = compute_hwid()

    def _default_storage_path(self) -> Path:
        appdata = Path(os.getenv("APPDATA") or Path.home() / ".config")
        return appdata / APP_STORAGE_SUBDIR

    def _discover_license_path(self) -> Path:
        possible = [self.base_path / LICENSE_FILENAME, Path.cwd() / LICENSE_FILENAME]
        for candidate in possible:
            if candidate.exists():
                return candidate
        # fallback to base path even if missing; user must provide
        return self.base_path / LICENSE_FILENAME

    def load(self) -> None:
        if not self.license_path.exists():
            raise FileNotFoundError("License file not found. Please place license.jbslic next to the executable.")
        license_document = json.loads(self.license_path.read_text(encoding="utf-8"))
        payload = extract_signed_document(license_document, self.public_key)
        self.license = License.from_payload(payload)

        password = self.license.license_id
        activations_path = self.base_path / ACTIVATIONS_FILENAME
        state_path = self.base_path / STATE_FILENAME
        stored_activations = decrypt_json_from_file_or_default(activations_path, password, {"license_id": self.license.license_id, "devices": []})
        self.activation_state = ActivationState.from_serializable(stored_activations)
        self.activation_state.license_id = self.license.license_id

        self.state_data = decrypt_json_from_file_or_default(state_path, password, {"last_seen_utc": datetime.now(timezone.utc).isoformat()})
        last_seen = datetime.fromisoformat(self.state_data["last_seen_utc"]).astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        if now < last_seen:
            raise TimeRollbackDetected("System clock appears to have moved backwards")
        self.state_data["last_seen_utc"] = now.isoformat()
        encrypt_json_to_file(state_path, self.state_data, password)

    # Public API ---------------------------------------------------------

    def is_device_authorized(self) -> bool:
        record = self.activation_state.get_record_for_hwid(self.current_hwid)
        if not record:
            return False
        if not self.license:
            return False
        if not self.license.is_lifetime and self.license.expires_utc and datetime.now(timezone.utc) > self.license.expires_utc:
            return False
        return True

    def active_device_count(self) -> int:
        return len(self.activation_state.devices)

    def create_activation_request(self, destination: Path) -> Dict[str, str]:
        if not self.license:
            raise RuntimeError("License not loaded")
        payload = {
            "license_id": self.license.license_id,
            "hwid": self.current_hwid,
            "client_version": "1.0",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "nonce": secrets.token_hex(16),
            "want_info": {
                "hostname": platform.node(),
                "os": platform.platform(),
            },
        }
        destination = destination.with_suffix(REQUEST_EXTENSION)
        destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def import_activation_response(self, source: Path) -> ActivationRecord:
        if not self.license:
            raise RuntimeError("License not loaded")
        document = json.loads(source.read_text(encoding="utf-8"))
        payload = extract_signed_document(document, self.public_key)
        if payload["license_id"] != self.license.license_id:
            raise ValueError("Activation response does not belong to this license")
        if payload["approved_hwid"] != self.current_hwid:
            raise ValueError("Activation response belongs to another device")
        record = ActivationRecord.from_payload(payload)
        self.activation_state.upsert_record(record)
        password = self.license.license_id
        encrypt_json_to_file(self.base_path / ACTIVATIONS_FILENAME, self.activation_state.to_serializable(), password)
        self._touch_state()
        return record

    def create_deactivation_request(self, destination: Path) -> Dict[str, str]:
        if not self.license:
            raise RuntimeError("License not loaded")
        payload = {
            "license_id": self.license.license_id,
            "hwid": self.current_hwid,
            "reason": "device decommissioned",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "nonce": secrets.token_hex(16),
        }
        destination = destination.with_suffix(DEACTIVATION_EXTENSION)
        destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def import_deactivation_response(self, source: Path) -> None:
        if not self.license:
            raise RuntimeError("License not loaded")
        document = json.loads(source.read_text(encoding="utf-8"))
        payload = extract_signed_document(document, self.public_key)
        if payload["license_id"] != self.license.license_id:
            raise ValueError("Response does not belong to this license")
        if payload.get("approved") is not True:
            raise ValueError("Deactivation response not approved")
        self.activation_state.remove_record(payload["hwid"])
        password = self.license.license_id
        encrypt_json_to_file(self.base_path / ACTIVATIONS_FILENAME, self.activation_state.to_serializable(), password)
        self._touch_state()

    def _touch_state(self) -> None:
        if not self.license:
            return
        now = datetime.now(timezone.utc).isoformat()
        self.state_data["last_seen_utc"] = now
        encrypt_json_to_file(self.base_path / STATE_FILENAME, self.state_data, self.license.license_id)


__all__ = [
    "License",
    "ActivationRecord",
    "ActivationState",
    "LicenseManager",
    "TimeRollbackDetected",
]
