"""Common serialisation helpers for the JBS licensing formats.

The file structure is intentionally simple and fully described in the
project documentation.  Each logical payload is first serialised to JSON,
optionally encrypted with AES-256-GCM and finally signed with RSA.
"""
from __future__ import annotations

import base64
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Type, TypeVar

from cryptography.hazmat.primitives.asymmetric import rsa

from .crypto import AES_KEY_SIZE, aes_decrypt, aes_encrypt, sign, verify

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


T = TypeVar("T")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime(ISO_FORMAT)


def from_iso(value: str) -> datetime:
    return datetime.strptime(value, ISO_FORMAT).replace(tzinfo=timezone.utc)


@dataclass(slots=True)
class SignedEnvelope:
    version: int
    payload: Dict[str, Any]
    signature: bytes
    encrypted: bool = False
    nonce: Optional[bytes] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "version": self.version,
            "signature": base64.b64encode(self.signature).decode("ascii"),
            "encrypted": self.encrypted,
        }
        if self.encrypted:
            assert self.nonce is not None
            data["nonce"] = base64.b64encode(self.nonce).decode("ascii")
            data["ciphertext"] = base64.b64encode(json.dumps(self.payload).encode("utf-8")).decode("ascii")
        else:
            data["payload"] = base64.b64encode(json.dumps(self.payload).encode("utf-8")).decode("ascii")
        return data

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        signature = base64.b64decode(data["signature"])
        encrypted = data.get("encrypted", False)
        if encrypted:
            nonce = base64.b64decode(data["nonce"])
            raw = base64.b64decode(data["ciphertext"])
            payload = json.loads(raw.decode("utf-8"))
            return cls(version=data["version"], payload=payload, signature=signature, encrypted=True, nonce=nonce)
        raw = base64.b64decode(data["payload"])
        payload = json.loads(raw.decode("utf-8"))
        return cls(version=data["version"], payload=payload, signature=signature, encrypted=False, nonce=None)


@dataclass(slots=True)
class LicensePayload:
    license_id: str
    plan: str
    issued_utc: str
    expires_utc: Optional[str]
    max_devices: int
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ActivationRequest:
    license_id: str
    hwid: str
    client_version: str
    timestamp_utc: str
    nonce: str
    want_info: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ActivationResponse:
    license_id: str
    approval: bool
    approved_hwid: str
    approved_at_utc: str
    device_index: int
    max_devices: int
    plan: str
    expires_utc: Optional[str]
    remark: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DeactivationRequest:
    license_id: str
    hwid: str
    reason: str
    timestamp_utc: str
    nonce: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DeactivationResponse:
    license_id: str
    hwid: str
    approved: bool
    approved_at_utc: str
    remark: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def pack_payload(payload: Dict[str, Any], private_key: rsa.RSAPrivateKey, *, encryption_key: Optional[bytes] = None) -> Dict[str, Any]:
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    envelope: Dict[str, Any]
    if encryption_key:
        if len(encryption_key) != AES_KEY_SIZE:
            raise ValueError("Invalid AES key length")
        nonce, ciphertext = aes_encrypt(encryption_key, raw)
        body = {
            "version": 1,
            "encrypted": True,
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        }
        signed_payload = json.dumps({"nonce": body["nonce"], "ciphertext": body["ciphertext"]}, sort_keys=True).encode("utf-8")
    else:
        body = {
            "version": 1,
            "encrypted": False,
            "payload": base64.b64encode(raw).decode("ascii"),
        }
        signed_payload = raw
    signature = sign(private_key, signed_payload)
    body["signature"] = base64.b64encode(signature).decode("ascii")
    return body


def unpack_payload(data: Dict[str, Any], public_key: rsa.RSAPublicKey, *, encryption_key: Optional[bytes] = None) -> Dict[str, Any]:
    signature = base64.b64decode(data["signature"])
    if data.get("encrypted"):
        if encryption_key is None:
            raise ValueError("Encrypted payload requires encryption key")
        nonce = base64.b64decode(data["nonce"])
        ciphertext = base64.b64decode(data["ciphertext"])
        signed_payload = json.dumps({"nonce": data["nonce"], "ciphertext": data["ciphertext"]}, sort_keys=True).encode("utf-8")
        verify(public_key, signed_payload, signature)
        raw = aes_decrypt(encryption_key, nonce, ciphertext)
    else:
        raw = base64.b64decode(data["payload"])
        verify(public_key, raw, signature)
    return json.loads(raw.decode("utf-8"))


def write_envelope(path: Path, envelope: Dict[str, Any]) -> None:
    path.write_text(json.dumps(envelope, indent=2))


def read_envelope(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())
