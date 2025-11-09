from __future__ import annotations

import os

from jbs_common import crypto


def test_sign_verify_roundtrip():
    private, public = crypto.generate_rsa_keypair()
    payload = b"hello world"
    signature = crypto.sign(private, payload)
    crypto.verify(public, payload, signature)


def test_aes_encrypt_decrypt():
    key = os.urandom(32)
    nonce, ciphertext = crypto.aes_encrypt(key, b"secret")
    plaintext = crypto.aes_decrypt(key, nonce, ciphertext)
    assert plaintext == b"secret"


def test_password_derivation_is_deterministic():
    key1, salt = crypto.derive_key_from_password("password")
    key2, _ = crypto.derive_key_from_password("password", salt)
    assert key1 == key2
