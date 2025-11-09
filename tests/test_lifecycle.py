from __future__ import annotations

import json
from pathlib import Path

import pytest

from jbs_client.licensing import LicenseManager
from jbs_generator.service import LicenseGeneratorService


@pytest.fixture()
def temp_service(tmp_path):
    db_path = tmp_path / "db.sqlite3"
    private_path = tmp_path / "private.pem"
    public_path = tmp_path / "public.pem"
    service = LicenseGeneratorService(db_path, private_path, public_path)
    service.ensure_keys()
    yield service
    service.shutdown()


def _create_master_binary(path: Path) -> Path:
    target = path / "JBS_master.exe"
    target.write_text("placeholder")
    return target


def test_full_activation_lifecycle(tmp_path, temp_service):
    service = temp_service
    master = _create_master_binary(tmp_path)
    output_dir = tmp_path / "packages"
    packages = service.create_license_packages(
        count=1,
        plan="annual",
        max_devices=2,
        output_dir=output_dir,
        prefix="TEST_",
        master_binary=master,
    )
    package = packages[0]
    license_path = package.license_file
    public_key = service.private_key.public_key()

    storage1 = tmp_path / "client1"
    manager1 = LicenseManager(storage1, public_key)
    manager1.import_license(license_path)
    hwid1 = "HWID1"
    req1_path = tmp_path / "req1.jbsreq"
    manager1.export_activation_request(req1_path, hwid1, "1.0.0", {"hostname": "pc1"})
    request1 = service.load_activation_request(req1_path)
    envelope1 = service.issue_activation_response(request1)
    act1_path = tmp_path / "act1.jbsact"
    act1_path.write_text(json.dumps(envelope1, indent=2))
    manager1.import_activation_file(act1_path)
    assert manager1.is_active_for_hwid(hwid1)

    storage2 = tmp_path / "client2"
    manager2 = LicenseManager(storage2, public_key)
    manager2.import_license(license_path)
    hwid2 = "HWID2"
    req2_path = tmp_path / "req2.jbsreq"
    manager2.export_activation_request(req2_path, hwid2, "1.0.0", {"hostname": "pc2"})
    request2 = service.load_activation_request(req2_path)
    envelope2 = service.issue_activation_response(request2)
    act2_path = tmp_path / "act2.jbsact"
    act2_path.write_text(json.dumps(envelope2, indent=2))
    manager2.import_activation_file(act2_path)
    assert manager2.is_active_for_hwid(hwid2)

    # third activation should fail because slots exhausted
    req3_path = tmp_path / "req3.jbsreq"
    manager2.export_activation_request(req3_path, "HWID3", "1.0.0", {})
    request3 = service.load_activation_request(req3_path)
    with pytest.raises(Exception):
        service.issue_activation_response(request3)

    # deactivate first device
    unreq_path = tmp_path / "unreq.jbsunreq"
    manager1.export_deactivation_request(unreq_path, hwid1, "replace")
    deact_request = service.load_deactivation_request(unreq_path)
    envelope_unact = service.issue_deactivation_response(deact_request)
    unact_path = tmp_path / "unact.jbsunact"
    unact_path.write_text(json.dumps(envelope_unact, indent=2))
    manager1.import_deactivation_file(unact_path)
    assert not manager1.is_active_for_hwid(hwid1)

    # new device should now fit into freed slot
    manager2.export_activation_request(req3_path, "HWID3", "1.0.0", {})
    request3b = service.load_activation_request(req3_path)
    envelope3 = service.issue_activation_response(request3b)
    act3_path = tmp_path / "act3.jbsact"
    act3_path.write_text(json.dumps(envelope3, indent=2))
    storage3 = tmp_path / "client3"
    manager3 = LicenseManager(storage3, public_key)
    manager3.import_license(license_path)
    manager3.import_activation_file(act3_path)
    assert manager3.is_active_for_hwid("HWID3")
