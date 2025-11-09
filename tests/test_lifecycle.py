from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from jbs_common.crypto import generate_rsa_keypair, serialize_public_key
from jbs_common.storage import encrypt_json_to_file
from generator.licensing import (
    LicenseConfig,
    create_activation_response,
    create_deactivation_response,
    create_license_payload,
    write_license_file,
)
from jbs_client.licensing import (
    ACTIVATION_EXTENSION,
    DEACTIVATION_EXTENSION,
    LICENSE_FILENAME,
    STATE_FILENAME,
    LicenseManager,
    TimeRollbackDetected,
)


def test_full_activation_cycle(tmp_path):
    private_key, public_key = generate_rsa_keypair(key_size=2048)
    config = LicenseConfig(plan="annual", max_devices=2)
    payload = create_license_payload(config)
    license_path = tmp_path / LICENSE_FILENAME
    write_license_file(license_path, payload, private_key)

    manager = LicenseManager(serialize_public_key(public_key), base_path=tmp_path)
    manager.load()
    assert not manager.is_device_authorized()

    req_path = tmp_path / "activation"
    request_payload = manager.create_activation_request(req_path)
    assert req_path.with_suffix(".jbsreq").exists()

    activation_document = create_activation_response(
        private_key,
        license_id=payload["license_id"],
        hwid=request_payload["hwid"],
        device_index=1,
        max_devices=payload["max_devices"],
        plan=payload["plan"],
        expires_utc=payload["expires_utc"],
    )
    activation_path = tmp_path / f"{payload['license_id']}{ACTIVATION_EXTENSION}"
    activation_path.write_text(json.dumps(activation_document), encoding="utf-8")
    manager.import_activation_response(activation_path)
    assert manager.is_device_authorized()
    assert manager.active_device_count() == 1

    deactivation_req_path = tmp_path / "deactivation"
    manager.create_deactivation_request(deactivation_req_path)
    deactivation_document = create_deactivation_response(
        private_key,
        license_id=payload["license_id"],
        hwid=request_payload["hwid"],
    )
    deactivation_path = tmp_path / f"{payload['license_id']}{DEACTIVATION_EXTENSION}"
    deactivation_path.write_text(json.dumps(deactivation_document), encoding="utf-8")
    manager.import_deactivation_response(deactivation_path)
    assert manager.active_device_count() == 0

    future = datetime.now(timezone.utc) + timedelta(days=1)
    encrypt_json_to_file(tmp_path / STATE_FILENAME, {"last_seen_utc": future.isoformat()}, payload["license_id"])
    manager2 = LicenseManager(serialize_public_key(public_key), base_path=tmp_path)
    with pytest.raises(TimeRollbackDetected):
        manager2.load()
