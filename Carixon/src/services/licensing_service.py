from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from ..utils.logger import get_logger
from ..utils.paths import CONFIG_DIR


@dataclass(slots=True)
class LicenseStatus:
    valid: bool
    reason: str = ""
    expires_at: Optional[datetime] = None
    license_id: Optional[str] = None
    remaining_seconds: Optional[int] = None

    @property
    def expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at


class LicensingService:
    def __init__(self, license_filename: str = "license.json") -> None:
        self._license_path = CONFIG_DIR / license_filename
        self._logger = get_logger("LicensingService")

    def _load_license(self) -> dict[str, str]:
        if not self._license_path.exists():
            raise FileNotFoundError("license.json not found")
        return json.loads(self._license_path.read_text(encoding="utf-8"))

    def _hash_hwid(self) -> str:
        components = [
            os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "unknown",
            os.environ.get("PROCESSOR_IDENTIFIER", ""),
            os.environ.get("USERNAME") or os.environ.get("USER") or "",
        ]
        fingerprint = "|".join(component.lower() for component in components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _load_public_key(self) -> Optional[ec.EllipticCurvePublicKey]:
        public_key_path = CONFIG_DIR / "license_public_key.pem"
        if not public_key_path.exists():
            self._logger.warning("Public key not found, falling back to demo signature validation.")
            return None
        key_bytes = public_key_path.read_bytes()
        return serialization.load_pem_public_key(key_bytes)

    def verify(self) -> LicenseStatus:
        try:
            payload = self._load_license()
        except FileNotFoundError:
            return LicenseStatus(valid=False, reason="missing_license")

        expires_at = datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00"))
        license_id = payload.get("license_id")
        max_devices = int(payload.get("max_devices", 1))
        signature_b64 = payload.get("signature", "")

        hwid_hash = self._hash_hwid()
        expected_hash = payload.get("hwid_hash")
        if expected_hash and expected_hash != hwid_hash:
            self._logger.warning("HWID mismatch: expected %s got %s", expected_hash, hwid_hash)
            return LicenseStatus(valid=False, reason="hwid_mismatch", expires_at=expires_at, license_id=license_id)

        public_key = self._load_public_key()
        message = f"{license_id}|{expires_at.isoformat()}|{max_devices}|{hwid_hash}".encode("utf-8")

        if public_key and signature_b64:
            try:
                signature = base64.b64decode(signature_b64)
                public_key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
            except (InvalidSignature, ValueError) as exc:  # pragma: no cover - critical path
                self._logger.error("Invalid license signature: %s", exc)
                return LicenseStatus(valid=False, reason="invalid_signature", expires_at=expires_at, license_id=license_id)
        else:
            if signature_b64 != "demo-signature":
                return LicenseStatus(valid=False, reason="missing_public_key", expires_at=expires_at, license_id=license_id)

        remaining_seconds = int((expires_at - datetime.now(timezone.utc)).total_seconds())
        if remaining_seconds < 0:
            return LicenseStatus(valid=False, reason="expired", expires_at=expires_at, license_id=license_id)

        self._logger.info("License %s validated, expires at %s", license_id, expires_at.isoformat())
        return LicenseStatus(
            valid=True,
            reason="ok",
            expires_at=expires_at,
            license_id=license_id,
            remaining_seconds=remaining_seconds,
        )


licensing_service = LicensingService()
