"""PySide6 GUI for the JBS license generator."""
from __future__ import annotations

import base64
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from jbs_common.crypto import generate_rsa_keypair, load_private_key, serialize_private_key, serialize_public_key

from ..db import ActivationRow, GeneratorDatabase, LicenseRow
from ..licensing import (
    LicenseConfig,
    build_readme_text,
    create_activation_response,
    create_deactivation_response,
    create_license_payload,
    write_license_file,
)
from ..packaging import PackageBuilder


class GeneratorWindow(QMainWindow):
    def __init__(self, database: GeneratorDatabase) -> None:
        super().__init__()
        self.database = database
        self.private_key_path: Optional[Path] = None
        self.private_key = None

        self.setWindowTitle("JBS License Generator")
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.generate_tab = QWidget()
        self.activation_tab = QWidget()
        self.deactivation_tab = QWidget()

        self.tabs.addTab(self.generate_tab, "Packages")
        self.tabs.addTab(self.activation_tab, "Activations")
        self.tabs.addTab(self.deactivation_tab, "Deactivations")

        self._build_generate_tab()
        self._build_activation_tab()
        self._build_deactivation_tab()

        self._refresh_license_table()

    # ------------------------------------------------------------------
    def _build_generate_tab(self) -> None:
        layout = QVBoxLayout(self.generate_tab)

        form_layout = QGridLayout()
        layout.addLayout(form_layout)

        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 1000)
        self.count_spin.setValue(1)

        self.output_edit = QLineEdit(str(Path.cwd() / "packages"))
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_output)

        self.plan_combo = QComboBox()
        self.plan_combo.addItems(["annual", "lifetime"])

        self.max_devices_spin = QSpinBox()
        self.max_devices_spin.setRange(1, 10)
        self.max_devices_spin.setValue(2)

        self.prefix_edit = QLineEdit("JBS_User_")

        self.key_status_label = QLabel("No private key loaded")
        load_key_btn = QPushButton("Load private key")
        load_key_btn.clicked.connect(self._load_private_key)
        gen_key_btn = QPushButton("Generate new key pair")
        gen_key_btn.clicked.connect(self._generate_key_pair)
        export_public_btn = QPushButton("Export public key")
        export_public_btn.clicked.connect(self._export_public_key)

        row = 0
        form_layout.addWidget(QLabel("Packages"), row, 0)
        form_layout.addWidget(self.count_spin, row, 1)
        row += 1
        form_layout.addWidget(QLabel("Output directory"), row, 0)
        form_layout.addWidget(self.output_edit, row, 1)
        form_layout.addWidget(browse_btn, row, 2)
        row += 1
        form_layout.addWidget(QLabel("Plan"), row, 0)
        form_layout.addWidget(self.plan_combo, row, 1)
        row += 1
        form_layout.addWidget(QLabel("Max devices"), row, 0)
        form_layout.addWidget(self.max_devices_spin, row, 1)
        row += 1
        form_layout.addWidget(QLabel("Prefix"), row, 0)
        form_layout.addWidget(self.prefix_edit, row, 1)
        row += 1
        form_layout.addWidget(self.key_status_label, row, 0, 1, 2)
        form_layout.addWidget(load_key_btn, row, 2)
        row += 1
        form_layout.addWidget(gen_key_btn, row, 0, 1, 2)
        form_layout.addWidget(export_public_btn, row, 2)

        generate_btn = QPushButton("Generate packages")
        generate_btn.clicked.connect(self._generate_packages)
        layout.addWidget(generate_btn)

        self.license_table = QTableWidget(0, 5)
        self.license_table.setHorizontalHeaderLabels(["License ID", "Plan", "Issued", "Expires", "Max devices"])
        layout.addWidget(self.license_table)

    def _build_activation_tab(self) -> None:
        layout = QVBoxLayout(self.activation_tab)
        self.activation_info = QLabel("Load a .jbsreq file to issue an activation.")
        layout.addWidget(self.activation_info)
        load_btn = QPushButton("Load activation request")
        load_btn.clicked.connect(self._load_activation_request)
        layout.addWidget(load_btn)
        issue_btn = QPushButton("Issue activation response")
        issue_btn.clicked.connect(self._issue_activation)
        layout.addWidget(issue_btn)
        self._current_request: Optional[dict] = None

    def _build_deactivation_tab(self) -> None:
        layout = QVBoxLayout(self.deactivation_tab)
        self.deactivation_info = QLabel("Load a .jbsunreq file to approve a deactivation.")
        layout.addWidget(self.deactivation_info)
        load_btn = QPushButton("Load deactivation request")
        load_btn.clicked.connect(self._load_deactivation_request)
        layout.addWidget(load_btn)
        approve_btn = QPushButton("Issue deactivation approval")
        approve_btn.clicked.connect(self._issue_deactivation)
        layout.addWidget(approve_btn)
        self._current_deactivation: Optional[dict] = None

    # ------------------------------------------------------------------
    def _browse_output(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select output directory", self.output_edit.text())
        if directory:
            self.output_edit.setText(directory)

    def _load_private_key(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Load private key", filter="Private key (*.pem *.json)")
        if not filename:
            return
        path = Path(filename)
        try:
            data = path.read_bytes()
            if path.suffix == ".json":
                # encrypted container produced by encrypt_private_key
                from jbs_common.crypto import decrypt_private_key

                password, ok = QInputDialog.getText(self, "Password", "Enter password for private key:")  # pragma: no cover - interactive
                if not ok:
                    return
                self.private_key = decrypt_private_key(data, password)
            else:
                self.private_key = load_private_key(data)
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Private key", str(exc))
            return
        self.private_key_path = path
        self.key_status_label.setText(f"Loaded private key: {path.name}")

    def _generate_key_pair(self) -> None:
        private_key, public_key = generate_rsa_keypair()
        directory = QFileDialog.getExistingDirectory(self, "Select directory to store keys")
        if not directory:
            return
        directory_path = Path(directory)
        private_path = directory_path / "private.pem"
        public_path = directory_path / "public.pem"
        private_path.write_bytes(serialize_private_key(private_key))
        public_path.write_bytes(serialize_public_key(public_key))
        QMessageBox.information(self, "Key pair", f"Keys stored at {directory_path}")

    def _export_public_key(self) -> None:
        if not self.private_key:
            QMessageBox.warning(self, "Public key", "Load the private key first to export its public key.")
            return
        filename, _ = QFileDialog.getSaveFileName(self, "Export public key", "public.pem")
        if not filename:
            return
        Path(filename).write_bytes(serialize_public_key(self.private_key.public_key()))
        QMessageBox.information(self, "Public key", "Public key exported successfully.")

    def _generate_packages(self) -> None:
        if not self.private_key:
            QMessageBox.warning(self, "Private key", "Load or generate a private key before creating packages.")
            return
        output_dir = Path(self.output_edit.text())
        output_dir.mkdir(parents=True, exist_ok=True)
        builder = PackageBuilder(output_dir)
        readme = build_readme_text()
        count = self.count_spin.value()
        plan = self.plan_combo.currentText()
        max_devices = self.max_devices_spin.value()
        prefix = self.prefix_edit.text()
        master_exe = QFileDialog.getOpenFileName(self, "Select master JBS.exe", filter="Executable (*.exe)")[0]
        if not master_exe:
            return
        master_path = Path(master_exe)

        for i in range(1, count + 1):
            config = LicenseConfig(plan=plan, max_devices=max_devices)
            payload = create_license_payload(config)
            tmp_dir = Path(tempfile.mkdtemp())
            license_path = tmp_dir / "license.jbslic"
            write_license_file(license_path, payload, self.private_key)
            builder.build_package(prefix, i, master_path, license_path, readme)
            self.database.add_license(
                LicenseRow(
                    license_id=payload["license_id"],
                    plan=payload["plan"],
                    issued_utc=payload["issued_utc"],
                    expires_utc=payload["expires_utc"],
                    max_devices=payload["max_devices"],
                    note=payload.get("note", ""),
                    package_path=str(output_dir),
                )
            )
        QMessageBox.information(self, "Packages", f"Generated {count} package(s).")
        self._refresh_license_table()

    def _refresh_license_table(self) -> None:
        licenses = self.database.list_licenses()
        self.license_table.setRowCount(0)
        for row_data in licenses:
            row = self.license_table.rowCount()
            self.license_table.insertRow(row)
            self.license_table.setItem(row, 0, QTableWidgetItem(row_data.license_id))
            self.license_table.setItem(row, 1, QTableWidgetItem(row_data.plan))
            self.license_table.setItem(row, 2, QTableWidgetItem(row_data.issued_utc))
            self.license_table.setItem(row, 3, QTableWidgetItem(row_data.expires_utc or "∞"))
            self.license_table.setItem(row, 4, QTableWidgetItem(str(row_data.max_devices)))

    # Activation handling ------------------------------------------------
    def _load_activation_request(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Load activation request", filter="Requests (*.jbsreq)")
        if not filename:
            return
        data = json.loads(Path(filename).read_text(encoding="utf-8"))
        self._current_request = data
        self.activation_info.setText(json.dumps(data, indent=2))

    def _issue_activation(self) -> None:
        if not self.private_key:
            QMessageBox.warning(self, "Private key", "Load the private key first.")
            return
        if not self._current_request:
            QMessageBox.warning(self, "Activation", "Load a request file first.")
            return
        license_id = self._current_request["license_id"]
        license_row = self.database.get_license(license_id)
        if not license_row:
            QMessageBox.critical(self, "Activation", "License not found in the database.")
            return
        used = self.database.activation_count(license_id)
        if used >= license_row.max_devices:
            QMessageBox.critical(self, "Activation", "No device slots available for this license.")
            return
        device_index = used + 1
        document = create_activation_response(
            self.private_key,
            license_id=license_id,
            hwid=self._current_request["hwid"],
            device_index=device_index,
            max_devices=license_row.max_devices,
            plan=license_row.plan,
            expires_utc=license_row.expires_utc,
        )
        filename, _ = QFileDialog.getSaveFileName(self, "Save activation response", f"{license_id}.jbsact")
        if not filename:
            return
        Path(filename).write_text(json.dumps(document, indent=2), encoding="utf-8")
        if document.get("encrypted"):
            approved_at = datetime.now(timezone.utc).isoformat()
        else:
            payload = json.loads(base64.b64decode(document["payload"]).decode("utf-8"))
            approved_at = payload["approved_at_utc"]
        self.database.record_activation(
            ActivationRow(
                license_id=license_id,
                hwid=self._current_request["hwid"],
                approved_at_utc=approved_at,
                device_index=device_index,
                remark="",
            )
        )
        QMessageBox.information(self, "Activation", "Activation response created.")

    # Deactivation handling ---------------------------------------------
    def _load_deactivation_request(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Load deactivation request", filter="Requests (*.jbsunreq)")
        if not filename:
            return
        data = json.loads(Path(filename).read_text(encoding="utf-8"))
        self._current_deactivation = data
        self.deactivation_info.setText(json.dumps(data, indent=2))

    def _issue_deactivation(self) -> None:
        if not self.private_key:
            QMessageBox.warning(self, "Private key", "Load the private key first.")
            return
        if not self._current_deactivation:
            QMessageBox.warning(self, "Deactivation", "Load a request file first.")
            return
        license_id = self._current_deactivation["license_id"]
        document = create_deactivation_response(
            self.private_key,
            license_id=license_id,
            hwid=self._current_deactivation["hwid"],
        )
        filename, _ = QFileDialog.getSaveFileName(self, "Save deactivation approval", f"{license_id}.jbsunact")
        if not filename:
            return
        Path(filename).write_text(json.dumps(document, indent=2), encoding="utf-8")
        self.database.record_deactivation(license_id, self._current_deactivation["hwid"], "")
        QMessageBox.information(self, "Deactivation", "Deactivation approved and stored.")


def run_gui(database_path: Path) -> int:
    app = QApplication(sys.argv)
    database = GeneratorDatabase(database_path)
    window = GeneratorWindow(database)
    window.resize(900, 600)
    window.show()
    return app.exec()


__all__ = ["run_gui", "GeneratorWindow"]
