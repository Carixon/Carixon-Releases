from __future__ import annotations

import base64
import json

from jbs_common.crypto import (
    create_signed_document,
    extract_signed_document,
    generate_rsa_keypair,
)


def test_signed_document_roundtrip():
    private_key, public_key = generate_rsa_keypair(key_size=2048)
    payload = {"hello": "world", "answer": 42}
    document = create_signed_document(payload, private_key)
    extracted = extract_signed_document(document, public_key)
    assert extracted == payload


def test_signature_verification_fails_on_tamper():
    private_key, public_key = generate_rsa_keypair(key_size=2048)
    payload = {"data": "value"}
    document = create_signed_document(payload, private_key)
    tampered = dict(document)
    payload_bytes = base64.b64decode(tampered["payload"])
    payload_dict = json.loads(payload_bytes)
    payload_dict["data"] = "tampered"
    tampered["payload"] = base64.b64encode(json.dumps(payload_dict).encode("utf-8")).decode("ascii")
    try:
        extract_signed_document(tampered, public_key)
    except Exception:
        pass
    else:
        raise AssertionError("Signature verification should fail when payload is modified")
