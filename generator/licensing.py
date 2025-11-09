"""License and activation helpers for the generator."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

from cryptography.hazmat.primitives.asymmetric import rsa

from jbs_common.crypto import create_signed_document


@dataclass
class LicenseConfig:
    plan: str  # "annual" or "lifetime"
    max_devices: int = 2
    note: str = ""

    def compute_expiry(self) -> Optional[datetime]:
        if self.plan == "lifetime":
            return None
        return datetime.now(timezone.utc) + timedelta(days=365)


def create_license_payload(config: LicenseConfig) -> Dict[str, object]:
    issued = datetime.now(timezone.utc)
    expires = config.compute_expiry()
    payload = {
        "license_id": str(uuid.uuid4()),
        "plan": config.plan,
        "issued_utc": issued.isoformat(),
        "expires_utc": expires.isoformat() if expires else None,
        "max_devices": config.max_devices,
        "note": config.note,
    }
    return payload


def write_license_file(path: Path, payload: Dict[str, object], private_key: rsa.RSAPrivateKey) -> None:
    document = create_signed_document(payload, private_key)
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")


def create_activation_response(
    private_key: rsa.RSAPrivateKey,
    *,
    license_id: str,
    hwid: str,
    device_index: int,
    max_devices: int,
    plan: str,
    expires_utc: Optional[str],
    remark: str = "",
) -> Dict[str, object]:
    payload = {
        "license_id": license_id,
        "approval": True,
        "approved_hwid": hwid,
        "approved_at_utc": datetime.now(timezone.utc).isoformat(),
        "device_index": device_index,
        "max_devices": max_devices,
        "plan": plan,
        "expires_utc": expires_utc,
        "remark": remark,
    }
    return create_signed_document(payload, private_key)


def create_deactivation_response(
    private_key: rsa.RSAPrivateKey,
    *,
    license_id: str,
    hwid: str,
    remark: str = "",
) -> Dict[str, object]:
    payload = {
        "license_id": license_id,
        "hwid": hwid,
        "approved": True,
        "approved_at_utc": datetime.now(timezone.utc).isoformat(),
        "remark": remark,
    }
    return create_signed_document(payload, private_key)


def build_readme_text() -> str:
    return """JBS – Just Be Safe
=======================

1. Run JBS.exe
2. Create the activation request (.jbsreq)
3. Send it to Benjamin and wait for the signed activation (.jbsact)
4. Import the activation response to unlock the application

To move the license to another device:
1. On the old device create a deactivation request (.jbsunreq)
2. Send it to Benjamin and import the deactivation approval (.jbsunact)
3. Activate the new device via the standard activation workflow
"""


__all__ = [
    "LicenseConfig",
    "create_license_payload",
    "write_license_file",
    "create_activation_response",
    "create_deactivation_response",
    "build_readme_text",
]
