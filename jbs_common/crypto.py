"""Common cryptographic helpers shared by the generator and the client."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import secrets
import base64
from typing import Any, Dict, Optional, Tuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
try:  # pragma: no cover - optional dependency in test environment
    from argon2.low_level import hash_secret_raw, Type
except ModuleNotFoundError:  # pragma: no cover
    import hashlib

    class _FallbackType:
        ID = "argon2id"

    Type = _FallbackType()

    def hash_secret_raw(password: bytes, salt: bytes, time_cost: int, memory_cost: int, parallelism: int, hash_len: int, type: str):
        return hashlib.pbkdf2_hmac("sha256", password, salt, time_cost * 1000, dklen=hash_len)


JSON_SEPARATORS = (",", ":")


@dataclass
class EncryptedPayload:
    nonce: bytes
    ciphertext: bytes
    tag: bytes

    def to_json(self) -> Dict[str, str]:
        return {
            "nonce": base64.b64encode(self.nonce).decode("ascii"),
            "ciphertext": base64.b64encode(self.ciphertext).decode("ascii"),
            "tag": base64.b64encode(self.tag).decode("ascii"),
        }

    @classmethod
    def from_json(cls, data: Dict[str, str]) -> "EncryptedPayload":
        return cls(
            nonce=base64.b64decode(data["nonce"]),
            ciphertext=base64.b64decode(data["ciphertext"]),
            tag=base64.b64decode(data["tag"]),
        )


def generate_rsa_keypair(key_size: int = 3072) -> Tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    """Generate a RSA keypair suitable for signing payloads."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=key_size, backend=default_backend())
    return private_key, private_key.public_key()


def serialize_public_key(public_key: rsa.RSAPublicKey) -> bytes:
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def serialize_private_key(private_key: rsa.RSAPrivateKey) -> bytes:
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def encrypt_private_key(private_key: rsa.RSAPrivateKey, password: str) -> bytes:
    """Encrypt the PEM representation of *private_key* using Argon2id + AES-GCM.

    The function returns a JSON encoded byte-string.  The JSON schema is::

        {
            "version": 1,
            "salt": "...",  # base64
            "nonce": "...",  # base64
            "ciphertext": "...",  # base64
            "tag": "..."  # base64
        }
    """

    salt = secrets.token_bytes(16)
    key = hash_secret_raw(
        password.encode("utf-8"),
        salt,
        time_cost=3,
        memory_cost=1024 * 64,
        parallelism=4,
        hash_len=32,
        type=Type.ID,
    )
    pem = serialize_private_key(private_key)
    aes = AESGCM(key)
    nonce = secrets.token_bytes(12)
    ciphertext = aes.encrypt(nonce, pem, b"JBS-PRIVATE-KEY")
    payload = {
        "version": 1,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext[:-16]).decode("ascii"),
        "tag": base64.b64encode(ciphertext[-16:]).decode("ascii"),
    }
    return json.dumps(payload, separators=JSON_SEPARATORS).encode("utf-8")


def decrypt_private_key(data: bytes, password: str) -> rsa.RSAPrivateKey:
    payload = json.loads(data.decode("utf-8"))
    if payload.get("version") != 1:
        raise ValueError("Unsupported private key container version")
    salt = base64.b64decode(payload["salt"])
    key = hash_secret_raw(
        password.encode("utf-8"),
        salt,
        time_cost=3,
        memory_cost=1024 * 64,
        parallelism=4,
        hash_len=32,
        type=Type.ID,
    )
    nonce = base64.b64decode(payload["nonce"])
    ciphertext = base64.b64decode(payload["ciphertext"])
    tag = base64.b64decode(payload["tag"])
    aes = AESGCM(key)
    pem = aes.decrypt(nonce, ciphertext + tag, b"JBS-PRIVATE-KEY")
    return serialization.load_pem_private_key(pem, password=None)


def sign_blob(private_key: rsa.RSAPrivateKey, data: bytes) -> bytes:
    return private_key.sign(
        data,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


def verify_blob_signature(public_key: rsa.RSAPublicKey, signature: bytes, data: bytes) -> None:
    public_key.verify(signature, data, padding.PKCS1v15(), hashes.SHA256())


def _prepare_signature_payload(structure: Dict[str, Any]) -> bytes:
    return json.dumps(structure, sort_keys=True, separators=JSON_SEPARATORS).encode("utf-8")


def create_signed_document(
    payload: Dict[str, Any],
    private_key: rsa.RSAPrivateKey,
    *,
    encrypt: bool = False,
    encryption_key: Optional[bytes] = None,
    associated_data: bytes = b"",
) -> Dict[str, Any]:
    """Create a signed (and optionally encrypted) document.

    The resulting structure contains the following keys::

        {
            "version": 1,
            "encrypted": bool,
            "payload": "..."  # base64 encoded JSON when not encrypted
            # or
            "nonce": "...",
            "ciphertext": "...",
            "tag": "...",
            "signature": "..."
        }
    """

    if encrypt and not encryption_key:
        raise ValueError("Encryption requested but no key provided")

    payload_bytes = json.dumps(payload, sort_keys=True, separators=JSON_SEPARATORS).encode("utf-8")
    document: Dict[str, Any] = {
        "version": 1,
        "encrypted": bool(encrypt),
    }

    if encrypt:
        aes = AESGCM(encryption_key)
        nonce = secrets.token_bytes(12)
        ciphertext = aes.encrypt(nonce, payload_bytes, associated_data)
        document.update(
            {
                "nonce": base64.b64encode(nonce).decode("ascii"),
                "ciphertext": base64.b64encode(ciphertext[:-16]).decode("ascii"),
                "tag": base64.b64encode(ciphertext[-16:]).decode("ascii"),
            }
        )
    else:
        document["payload"] = base64.b64encode(payload_bytes).decode("ascii")

    to_sign = {k: v for k, v in document.items() if k != "signature"}
    signature = sign_blob(private_key, _prepare_signature_payload(to_sign))
    document["signature"] = base64.b64encode(signature).decode("ascii")
    return document


def extract_signed_document(
    document: Dict[str, Any],
    public_key: rsa.RSAPublicKey,
    *,
    decryption_key: Optional[bytes] = None,
    associated_data: bytes = b"",
) -> Dict[str, Any]:
    """Verify and extract a signed document."""

    signature_b64 = document.get("signature")
    if not signature_b64:
        raise ValueError("Document does not contain a signature")

    to_verify = {k: v for k, v in document.items() if k != "signature"}
    verify_blob_signature(public_key, base64.b64decode(signature_b64), _prepare_signature_payload(to_verify))

    encrypted = bool(document.get("encrypted"))
    if not encrypted:
        payload_b64 = document.get("payload")
        if payload_b64 is None:
            raise ValueError("Document missing payload")
        payload_bytes = base64.b64decode(payload_b64)
        return json.loads(payload_bytes.decode("utf-8"))

    if not decryption_key:
        raise ValueError("Encrypted document but no decryption key provided")

    nonce = base64.b64decode(document["nonce"])
    ciphertext = base64.b64decode(document["ciphertext"])
    tag = base64.b64decode(document["tag"])
    aes = AESGCM(decryption_key)
    payload_bytes = aes.decrypt(nonce, ciphertext + tag, associated_data)
    return json.loads(payload_bytes.decode("utf-8"))


def load_public_key(data: bytes) -> rsa.RSAPublicKey:
    return serialization.load_pem_public_key(data)


def load_private_key(data: bytes, password: Optional[bytes] = None) -> rsa.RSAPrivateKey:
    return serialization.load_pem_private_key(data, password=password)


__all__ = [
    "EncryptedPayload",
    "generate_rsa_keypair",
    "serialize_public_key",
    "serialize_private_key",
    "encrypt_private_key",
    "decrypt_private_key",
    "create_signed_document",
    "extract_signed_document",
    "load_public_key",
    "load_private_key",
]
