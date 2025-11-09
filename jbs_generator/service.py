"""High level operations for the JBS License Generator."""
from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional
from zipfile import ZipFile

from cryptography.hazmat.primitives.asymmetric import rsa

from jbs_common.crypto import generate_rsa_keypair, load_private_key, load_public_key, save_private_key, save_public_key
from jbs_common.formats import (
    ActivationRequest,
    ActivationResponse,
    DeactivationRequest,
    DeactivationResponse,
    LicensePayload,
    pack_payload,
    to_iso,
    utc_now,
)
from jbs_generator.database import LicenseDatabase, LicenseRecord


@dataclass(slots=True)
class PackageDefinition:
    license_record: LicenseRecord
    directory: Path
    license_file: Path
    readme_file: Path


class GeneratorError(RuntimeError):
    pass


class LicenseGeneratorService:
    def __init__(self, db_path: Path, private_key_path: Path, public_key_path: Path):
        self.db = LicenseDatabase(db_path)
        self.private_key_path = private_key_path
        self.public_key_path = public_key_path
        self.private_key: Optional[rsa.RSAPrivateKey] = None
        self.public_key: Optional[rsa.RSAPublicKey] = None

    # region Key management
    def ensure_keys(self) -> None:
        if self.private_key_path.exists() and self.public_key_path.exists():
            self.private_key = load_private_key(self.private_key_path)
            self.public_key = load_public_key(self.public_key_path)
            return
        priv, pub = generate_rsa_keypair()
        save_private_key(priv, self.private_key_path)
        save_public_key(pub, self.public_key_path)
        self.private_key = priv
        self.public_key = pub

    # endregion

    # region License creation
    def _compute_expiry(self, plan: str) -> Optional[str]:
        if plan == "lifetime":
            return None
        expires = utc_now() + timedelta(days=365)
        return to_iso(expires)

    def create_license_packages(
        self,
        count: int,
        plan: str,
        max_devices: int,
        output_dir: Path,
        prefix: str,
        master_binary: Path,
        note: str = "",
    ) -> List[PackageDefinition]:
        if not self.private_key:
            raise GeneratorError("Private key not loaded")
        output_dir.mkdir(parents=True, exist_ok=True)
        packages: List[PackageDefinition] = []
        for index in range(1, count + 1):
            license_id = str(uuid.uuid4())
            record = LicenseRecord(
                license_id=license_id,
                plan=plan,
                issued_utc=to_iso(utc_now()),
                expires_utc=self._compute_expiry(plan),
                max_devices=max_devices,
                note=note,
                archive_prefix=prefix,
            )
            self.db.insert_license(record)
            payload = LicensePayload(
                license_id=license_id,
                plan=plan,
                issued_utc=record.issued_utc,
                expires_utc=record.expires_utc,
                max_devices=max_devices,
                note=note,
            )
            envelope = pack_payload(payload.to_dict(), self.private_key)
            package_dir = output_dir / f"{prefix}{index:03d}"
            package_dir.mkdir(parents=True, exist_ok=True)
            license_file = package_dir / "license.jbslic"
            license_file.write_text(json.dumps(envelope, indent=2))
            readme = package_dir / "README.txt"
            readme.write_text(
                (
                    "JBS – Just Be Safe\n\n"
                    "EN: 1) Run JBS.exe 2) Create activation request (.jbsreq) 3) Send the file to Benjamin "
                    "4) Import received .jbsact 5) Repeat for additional device slots (max {max_devices}) 6) For deactivation use the app.\n"
                    "DE: 1) Start JBS.exe 2) Aktivierungsanfrage erstellen (.jbsreq) 3) Datei an Benjamin senden "
                    "4) Erhaltene .jbsact importieren 5) Für weitere Geräte wiederholen (max {max_devices}) 6) Deaktivierung per App anstoßen.\n"
                    "CZ: 1) Spusťte JBS.exe 2) Vytvořte aktivační žádost (.jbsreq) 3) Odeslání Benjaminovi "
                    "4) Importujte doručený .jbsact 5) Opakujte pro další zařízení (max {max_devices}) 6) Deaktivaci řešte v aplikaci.\n"
                ).format(max_devices=max_devices)
            )
            target_binary = package_dir / "JBS.exe"
            shutil.copy2(master_binary, target_binary)
            archive_path = package_dir.with_suffix(".zip")
            with ZipFile(archive_path, "w") as archive:
                for file in [target_binary, license_file, readme]:
                    archive.write(file, arcname=file.name)
            packages.append(PackageDefinition(record, package_dir, license_file, readme))
            self.db.add_audit("license_created", {"license_id": license_id})
        return packages

    # endregion

    # region Activation lifecycle
    def load_activation_request(self, request_path: Path) -> ActivationRequest:
        data = json.loads(request_path.read_text())
        return ActivationRequest(**data)

    def issue_activation_response(self, request: ActivationRequest) -> Dict[str, any]:
        if not self.private_key:
            raise GeneratorError("Private key not loaded")
        record = self.db.fetch_license(request.license_id)
        if not record:
            raise GeneratorError("License not found")
        current = self.db.list_activations(request.license_id)
        if len(current) >= record.max_devices:
            raise GeneratorError("All device slots used")
        existing = [row for row in current if row["hwid"] == request.hwid]
        if existing:
            device_index = existing[0]["device_index"]
        else:
            device_index = len(current) + 1
            self.db.record_activation(request.license_id, request.hwid, device_index)
        response = ActivationResponse(
            license_id=request.license_id,
            approval=True,
            approved_hwid=request.hwid,
            approved_at_utc=to_iso(utc_now()),
            device_index=device_index,
            max_devices=record.max_devices,
            plan=record.plan,
            expires_utc=record.expires_utc,
            remark="",
        )
        envelope = pack_payload(response.to_dict(), self.private_key)
        self.db.add_audit("activation_approved", {"license_id": request.license_id, "hwid": request.hwid})
        return envelope

    def load_deactivation_request(self, request_path: Path) -> DeactivationRequest:
        data = json.loads(request_path.read_text())
        return DeactivationRequest(**data)

    def issue_deactivation_response(self, request: DeactivationRequest, remark: str = "") -> Dict[str, any]:
        if not self.private_key:
            raise GeneratorError("Private key not loaded")
        record = self.db.fetch_license(request.license_id)
        if not record:
            raise GeneratorError("License not found")
        self.db.remove_activation(request.license_id, request.hwid, remark)
        response = DeactivationResponse(
            license_id=request.license_id,
            hwid=request.hwid,
            approved=True,
            approved_at_utc=to_iso(utc_now()),
            remark=remark,
        )
        envelope = pack_payload(response.to_dict(), self.private_key)
        self.db.add_audit("deactivation_approved", {"license_id": request.license_id, "hwid": request.hwid})
        return envelope

    # endregion

    def export_public_key(self, target_path: Path) -> None:
        if not self.public_key:
            raise GeneratorError("Public key unavailable")
        save_public_key(self.public_key, target_path)

    def shutdown(self) -> None:
        self.db.close()
