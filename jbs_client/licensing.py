"""Core licensing logic for the offline JBS client."""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives.asymmetric import rsa

from jbs_common.crypto import AES_KEY_SIZE, aes_decrypt, aes_encrypt, derive_local_key
from jbs_common.formats import (
    ActivationRequest,
    ActivationResponse,
    DeactivationRequest,
    DeactivationResponse,
    LicensePayload,
    from_iso,
    pack_payload,
    read_envelope,
    to_iso,
    unpack_payload,
    utc_now,
)


STATE_FILENAME = "state.dat"
ACTIVATIONS_FILENAME = "activations.dat"
LICENSE_FILENAME = "license.jbslic"


class LicenseError(RuntimeError):
    """Base error raised for licensing issues."""


@dataclass(slots=True)
class ActivationRecord:
    hwid: str
    approved_at_utc: str
    device_index: int


class FileExchangeMixin:
    """Utility helpers used by the GUI layer for import/export."""

    def export_activation_request(self, target_path: Path, hwid: str, client_version: str, want_info: Optional[Dict[str, str]] = None) -> None:
        payload = self.create_activation_request(hwid, client_version, want_info)
        write_activation_request(target_path, payload)

    def import_activation_file(self, path: Path) -> None:
        data = read_envelope(path)
        payload = unpack_payload(data, self.public_key)
        self.apply_activation_response(payload)

    def export_deactivation_request(self, target_path: Path, hwid: str, reason: str) -> None:
        payload = self.create_deactivation_request(hwid, reason)
        write_activation_request(target_path, payload)

    def import_deactivation_file(self, path: Path) -> None:
        data = read_envelope(path)
        payload = unpack_payload(data, self.public_key)
        self.apply_deactivation_response(payload)


class LicenseManager(FileExchangeMixin):
    def __init__(self, storage_dir: Path, public_key: rsa.RSAPublicKey):
        self.storage_dir = storage_dir
        self.public_key = public_key
        self.license_payload: Optional[LicensePayload] = None
        self._state: Dict[str, Any] = {"last_seen_utc": None}
        self._activations: Dict[str, ActivationRecord] = {}
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    # region Persistence helpers
    def _state_path(self) -> Path:
        return self.storage_dir / STATE_FILENAME

    def _activations_path(self) -> Path:
        return self.storage_dir / ACTIVATIONS_FILENAME

    def _license_path(self) -> Path:
        return self.storage_dir / LICENSE_FILENAME

    def _encryption_key(self) -> bytes:
        if not self.license_payload:
            raise LicenseError("License not loaded")
        return derive_local_key(self.license_payload.license_id)

    def _read_encrypted_file(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        key = self._encryption_key()
        raw = json.loads(path.read_text())
        nonce = base64.b64decode(raw["nonce"]) if isinstance(raw.get("nonce"), str) else bytes(raw.get("nonce", b""))
        ciphertext = base64.b64decode(raw["ciphertext"]) if isinstance(raw.get("ciphertext"), str) else bytes(raw.get("ciphertext", b""))
        if len(key) != AES_KEY_SIZE:
            raise LicenseError("Invalid encryption key length")
        plaintext = aes_decrypt(key, nonce, ciphertext)
        return json.loads(plaintext.decode("utf-8"))

    def _write_encrypted_file(self, path: Path, payload: Dict[str, Any]) -> None:
        if not self.license_payload:
            raise LicenseError("License not loaded")
        key = self._encryption_key()
        nonce, ciphertext = aes_encrypt(key, json.dumps(payload).encode("utf-8"))
        data = {
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        }
        path.write_text(json.dumps(data, indent=2))

    def _load_state(self) -> None:
        if not self.license_payload:
            return
        self._state = self._read_encrypted_file(self._state_path()) or {"last_seen_utc": None}

    def _save_state(self) -> None:
        if not self.license_payload:
            return
        self._write_encrypted_file(self._state_path(), self._state)

    def _load_activations(self) -> None:
        if not self.license_payload:
            return
        content = self._read_encrypted_file(self._activations_path())
        self._activations = {
            item["hwid"]: ActivationRecord(
                hwid=item["hwid"],
                approved_at_utc=item["approved_at_utc"],
                device_index=item["device_index"],
            )
            for item in content.get("activations", [])
        }

    def _save_activations(self) -> None:
        if not self.license_payload:
            return
        payload = {
            "license_id": self.license_payload.license_id,
            "activations": [
                {
                    "hwid": record.hwid,
                    "approved_at_utc": record.approved_at_utc,
                    "device_index": record.device_index,
                }
                for record in self._activations.values()
            ],
        }
        self._write_encrypted_file(self._activations_path(), payload)

    # endregion

    # region License lifecycle
    def import_license(self, license_path: Path) -> None:
        data = read_envelope(license_path)
        payload_dict = unpack_payload(data, self.public_key)
        self.license_payload = LicensePayload(**payload_dict)
        self._license_path().write_text(json.dumps(data, indent=2))
        self._load_state()
        self._load_activations()

    def load_existing_license(self) -> None:
        path = self._license_path()
        if not path.exists():
            raise LicenseError("No license found in storage")
        data = read_envelope(path)
        payload_dict = unpack_payload(data, self.public_key)
        self.license_payload = LicensePayload(**payload_dict)
        self._load_state()
        self._load_activations()

    def check_time_anomaly(self) -> Optional[str]:
        last_seen = self._state.get("last_seen_utc")
        now = utc_now()
        self._state["last_seen_utc"] = to_iso(now)
        self._save_state()
        if last_seen is None:
            return None
        last_dt = from_iso(last_seen)
        if last_dt > now:
            return "time_rollback_detected"
        return None

    def is_active_for_hwid(self, hwid: str) -> bool:
        return hwid in self._activations

    def activated_devices(self) -> List[ActivationRecord]:
        return list(self._activations.values())

    def remaining_slots(self) -> int:
        if not self.license_payload:
            raise LicenseError("License not loaded")
        return max(0, self.license_payload.max_devices - len(self._activations))

    def is_expired(self) -> bool:
        if not self.license_payload:
            raise LicenseError("License not loaded")
        if self.license_payload.expires_utc is None:
            return False
        expires = from_iso(self.license_payload.expires_utc)
        return utc_now() > expires

    # endregion

    # region Request generation
    def create_activation_request(self, hwid: str, client_version: str, want_info: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        if not self.license_payload:
            raise LicenseError("License not loaded")
        want_info = want_info or {}
        req = ActivationRequest(
            license_id=self.license_payload.license_id,
            hwid=hwid,
            client_version=client_version,
            timestamp_utc=to_iso(utc_now()),
            nonce=base64.b64encode(derive_local_key(hwid))[:24].decode("ascii"),
            want_info=want_info,
        )
        return req.to_dict()

    def create_deactivation_request(self, hwid: str, reason: str) -> Dict[str, Any]:
        if hwid not in self._activations:
            raise LicenseError("Device not activated")
        req = DeactivationRequest(
            license_id=self.license_payload.license_id,
            hwid=hwid,
            reason=reason,
            timestamp_utc=to_iso(utc_now()),
            nonce=base64.b64encode(derive_local_key(hwid))[:24].decode("ascii"),
        )
        return req.to_dict()

    # endregion

    # region Import responses
    def apply_activation_response(self, response_data: Dict[str, Any]) -> None:
        if not self.license_payload:
            raise LicenseError("License not loaded")
        payload = ActivationResponse(**response_data)
        if payload.license_id != self.license_payload.license_id:
            raise LicenseError("Activation license mismatch")
        if not payload.approval:
            raise LicenseError("Activation declined")
        if payload.approved_hwid in self._activations:
            return
        if len(self._activations) >= self.license_payload.max_devices:
            raise LicenseError("No slots available")
        self._activations[payload.approved_hwid] = ActivationRecord(
            hwid=payload.approved_hwid,
            approved_at_utc=payload.approved_at_utc,
            device_index=payload.device_index,
        )
        self._save_activations()

    def apply_deactivation_response(self, response_data: Dict[str, Any]) -> None:
        if not self.license_payload:
            raise LicenseError("License not loaded")
        payload = DeactivationResponse(**response_data)
        if payload.license_id != self.license_payload.license_id:
            raise LicenseError("Deactivation license mismatch")
        if not payload.approved:
            raise LicenseError("Deactivation declined")
        self._activations.pop(payload.hwid, None)
        self._save_activations()

    # endregion


def serialize_envelope(payload: Dict[str, Any], private_key: rsa.RSAPrivateKey) -> Dict[str, Any]:
    return pack_payload(payload, private_key)


def write_activation_request(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2))


def read_activation_request(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())
