"""Common cryptographic utilities for the JBS licensing suite.

This module centralises generation of RSA keys, AES-GCM helpers and
Argon2id based password wrapping that are shared between the client and
generator applications.  The functions are intentionally small so that
they can easily be reused from GUI layers or the automated tests.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import (
    BestAvailableEncryption,
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from os import urandom

try:  # pragma: no cover - optional dependency
    from argon2.low_level import Type, hash_secret
    HAS_ARGON2 = True
except ModuleNotFoundError:  # pragma: no cover - fallback when argon2-cffi unavailable
    HAS_ARGON2 = False


RSA_KEY_SIZE = 3072
RSA_PUBLIC_EXPONENT = 65537
AES_KEY_SIZE = 32
AES_NONCE_SIZE = 12
ARGON2_TIME_COST = 4
ARGON2_MEMORY_COST = 102400  # ~100 MiB
ARGON2_PARALLELISM = 8
ARGON2_SALT_SIZE = 16


@dataclass(slots=True)
class EncryptedPrivateKey:
    """Container holding an encrypted RSA private key blob."""

    ciphertext: bytes
    salt: bytes
    nonce: bytes

    def serialize(self) -> bytes:
        return self.salt + self.nonce + self.ciphertext

    @classmethod
    def deserialize(cls, payload: bytes) -> "EncryptedPrivateKey":
        if len(payload) < ARGON2_SALT_SIZE + AES_NONCE_SIZE:
            raise ValueError("Invalid payload length")
        salt = payload[:ARGON2_SALT_SIZE]
        nonce = payload[ARGON2_SALT_SIZE:ARGON2_SALT_SIZE + AES_NONCE_SIZE]
        ciphertext = payload[ARGON2_SALT_SIZE + AES_NONCE_SIZE:]
        return cls(ciphertext=ciphertext, salt=salt, nonce=nonce)


def generate_rsa_keypair() -> Tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    """Generate a new RSA key pair using the configured parameters."""

    private_key = rsa.generate_private_key(
        public_exponent=RSA_PUBLIC_EXPONENT,
        key_size=RSA_KEY_SIZE,
    )
    return private_key, private_key.public_key()


def save_private_key(private_key: rsa.RSAPrivateKey, path: Path, password: Optional[str] = None) -> None:
    """Persist a private key to disk, optionally password protected."""

    if password:
        encryption = BestAvailableEncryption(password.encode("utf-8"))
    else:
        encryption = NoEncryption()
    pem = private_key.private_bytes(
        Encoding.PEM,
        PrivateFormat.PKCS8,
        encryption,
    )
    path.write_bytes(pem)


def save_public_key(public_key: rsa.RSAPublicKey, path: Path) -> None:
    pem = public_key.public_bytes(
        Encoding.PEM,
        PublicFormat.SubjectPublicKeyInfo,
    )
    path.write_bytes(pem)


def load_private_key(path: Path, password: Optional[str] = None) -> rsa.RSAPrivateKey:
    data = path.read_bytes()
    return serialization.load_pem_private_key(data, password=password.encode("utf-8") if password else None)


def load_public_key(path: Path) -> rsa.RSAPublicKey:
    data = path.read_bytes()
    return serialization.load_pem_public_key(data)


def sign(private_key: rsa.RSAPrivateKey, payload: bytes) -> bytes:
    return private_key.sign(
        payload,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


def verify(public_key: rsa.RSAPublicKey, payload: bytes, signature: bytes) -> None:
    public_key.verify(
        signature,
        payload,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


def aes_encrypt(key: bytes, plaintext: bytes, associated_data: bytes = b"") -> Tuple[bytes, bytes]:
    if len(key) != AES_KEY_SIZE:
        raise ValueError("AES key must be 32 bytes")
    nonce = urandom(AES_NONCE_SIZE)
    aes = AESGCM(key)
    ciphertext = aes.encrypt(nonce, plaintext, associated_data)
    return nonce, ciphertext


def aes_decrypt(key: bytes, nonce: bytes, ciphertext: bytes, associated_data: bytes = b"") -> bytes:
    if len(key) != AES_KEY_SIZE:
        raise ValueError("AES key must be 32 bytes")
    aes = AESGCM(key)
    return aes.decrypt(nonce, ciphertext, associated_data)


def derive_key_from_password(password: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
    """Derive a 256-bit key using Argon2id.

    Returns the derived key and the salt used.  When *salt* is ``None`` a new
    random salt is generated.
    """

    if salt is None:
        salt = urandom(ARGON2_SALT_SIZE)
    if HAS_ARGON2:
        key = hash_secret(
            password.encode("utf-8"),
            salt,
            time_cost=ARGON2_TIME_COST,
            memory_cost=ARGON2_MEMORY_COST,
            parallelism=ARGON2_PARALLELISM,
            hash_len=AES_KEY_SIZE,
            type=Type.ID,
        )
    else:  # pragma: no cover - fallback for environments without argon2
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            200000,
            dklen=AES_KEY_SIZE,
        )
    return key, salt


def encrypt_private_key(private_key: rsa.RSAPrivateKey, password: str) -> EncryptedPrivateKey:
    key, salt = derive_key_from_password(password)
    nonce, ciphertext = aes_encrypt(key, private_key.private_bytes(
        Encoding.PEM,
        PrivateFormat.PKCS8,
        NoEncryption(),
    ))
    return EncryptedPrivateKey(ciphertext=ciphertext, salt=salt, nonce=nonce)


def decrypt_private_key(blob: EncryptedPrivateKey, password: str) -> rsa.RSAPrivateKey:
    key, _ = derive_key_from_password(password, blob.salt)
    pem = aes_decrypt(key, blob.nonce, blob.ciphertext)
    return serialization.load_pem_private_key(pem, password=None)


def derive_local_key(identifier: str) -> bytes:
    """Derive a deterministic AES key from an arbitrary identifier."""

    digest = hashlib.sha256(identifier.encode("utf-8")).digest()
    return digest[:AES_KEY_SIZE]
