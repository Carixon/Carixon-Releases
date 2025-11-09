from __future__ import annotations

from jbs_common import crypto
from jbs_common import formats
from jbs_common.hwid import HardwareFingerprint, fingerprint_hash


def test_pack_unpack_roundtrip():
    private, public = crypto.generate_rsa_keypair()
    payload = {"license_id": "abc", "plan": "annual"}
    envelope = formats.pack_payload(payload, private)
    recovered = formats.unpack_payload(envelope, public)
    assert recovered == payload


def test_license_payload_serialisation():
    payload = formats.LicensePayload(
        license_id="test",
        plan="annual",
        issued_utc="2024-01-01T00:00:00.000000Z",
        expires_utc=None,
        max_devices=2,
    )
    data = payload.to_dict()
    assert data["license_id"] == "test"


def test_hwid_hash_deterministic():
    fp = HardwareFingerprint(
        motherboard_serial="MB123",
        cpu_info="CPU",
        disk_serial="DISK",
        mac_addresses=["aa:bb:cc:dd:ee:ff"],
        os_installation_id="OS",
    )
    h1 = fingerprint_hash(fp)
    h2 = fingerprint_hash(fp)
    assert h1 == h2
    assert len(h1) == 24
