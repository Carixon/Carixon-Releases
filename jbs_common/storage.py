"""Encrypted JSON storage helpers."""
from __future__ import annotations

import base64
import json
import secrets
from pathlib import Path
from typing import Any, Dict

try:  # pragma: no cover - optional dependency in test environment
    from argon2.low_level import Type, hash_secret_raw
except ModuleNotFoundError:  # pragma: no cover
    import hashlib

    class _FallbackType:
        ID = "argon2id"

    Type = _FallbackType()

    def hash_secret_raw(password: bytes, salt: bytes, time_cost: int, memory_cost: int, parallelism: int, hash_len: int, type: str):
        return hashlib.pbkdf2_hmac("sha256", password, salt, time_cost * 1000, dklen=hash_len)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .crypto import JSON_SEPARATORS


def _derive_key(password: str, salt: bytes) -> bytes:
    return hash_secret_raw(
        password.encode("utf-8"),
        salt,
        time_cost=3,
        memory_cost=1024 * 32,
        parallelism=4,
        hash_len=32,
        type=Type.ID,
    )


def encrypt_json_to_file(path: Path, payload: Dict[str, Any], password: str) -> None:
    salt = secrets.token_bytes(16)
    key = _derive_key(password, salt)
    nonce = secrets.token_bytes(12)
    aes = AESGCM(key)
    plaintext = json.dumps(payload, sort_keys=True, separators=JSON_SEPARATORS).encode("utf-8")
    ciphertext = aes.encrypt(nonce, plaintext, b"JBS-STORAGE")
    container = {
        "version": 1,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext[:-16]).decode("ascii"),
        "tag": base64.b64encode(ciphertext[-16:]).decode("ascii"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(container, separators=JSON_SEPARATORS), encoding="utf-8")


def decrypt_json_from_file(path: Path, password: str) -> Dict[str, Any]:
    container = json.loads(path.read_text(encoding="utf-8"))
    if container.get("version") != 1:
        raise ValueError("Unsupported container version")
    salt = base64.b64decode(container["salt"])
    key = _derive_key(password, salt)
    nonce = base64.b64decode(container["nonce"])
    ciphertext = base64.b64decode(container["ciphertext"])
    tag = base64.b64decode(container["tag"])
    aes = AESGCM(key)
    plaintext = aes.decrypt(nonce, ciphertext + tag, b"JBS-STORAGE")
    return json.loads(plaintext.decode("utf-8"))


def decrypt_json_from_file_or_default(path: Path, password: str, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return default
    return decrypt_json_from_file(path, password)


__all__ = ["encrypt_json_to_file", "decrypt_json_from_file", "decrypt_json_from_file_or_default"]
