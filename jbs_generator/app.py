"""PySide6 user interface for the JBS License Generator."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from jbs_generator.service import GeneratorError, LicenseGeneratorService

APP_DIR = Path.home() / ".jbs_generator"
DB_PATH = APP_DIR / "generator.db"
PRIVATE_KEY_PATH = APP_DIR / "private.pem"
PUBLIC_KEY_PATH = APP_DIR / "public.pem"


class GeneratorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        APP_DIR.mkdir(parents=True, exist_ok=True)
        self.service = LicenseGeneratorService(DB_PATH, PRIVATE_KEY_PATH, PUBLIC_KEY_PATH)
        self.service.ensure_keys()

        self.setWindowTitle("JBS License Generator")
        self.resize(800, 600)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self._build_packages_tab()
        self._build_activation_tab()
        self._build_deactivation_tab()
        self._build_keys_tab()

    # region Tabs
    def _build_packages_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout()
        self.package_count = QSpinBox()
        self.package_count.setRange(1, 999)
        self.package_count.setValue(1)
        self.plan_combo = QComboBox()
        self.plan_combo.addItems(["annual", "lifetime"])
        self.max_devices = QSpinBox()
        self.max_devices.setRange(1, 10)
        self.max_devices.setValue(2)
        self.prefix_edit = QLineEdit("JBS_")
        self.output_edit = QLineEdit(str(APP_DIR / "packages"))
        browse_output = QPushButton("Browse")
        browse_output.clicked.connect(self._choose_output)
        self.master_binary_edit = QLineEdit()
        browse_master = QPushButton("Select JBS.exe")
        browse_master.clicked.connect(self._choose_master)
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        generate_button = QPushButton("Generate packages")
        generate_button.clicked.connect(self._generate_packages)

        layout.addRow("Packages", self.package_count)
        layout.addRow("Plan", self.plan_combo)
        layout.addRow("Max devices", self.max_devices)
        layout.addRow("Prefix", self.prefix_edit)
        row = QHBoxLayout()
        row.addWidget(self.output_edit)
        row.addWidget(browse_output)
        layout.addRow("Output", row)
        master_row = QHBoxLayout()
        master_row.addWidget(self.master_binary_edit)
        master_row.addWidget(browse_master)
        layout.addRow("Master binary", master_row)
        layout.addRow(generate_button)
        layout.addRow(QLabel("Log"))
        layout.addRow(self.log_widget)

        container = QWidget()
        container.setLayout(layout)
        tab_layout = QVBoxLayout()
        tab_layout.addWidget(container)
        tab.setLayout(tab_layout)
        self.tabs.addTab(tab, "Packages")

    def _build_activation_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout()
        self.activation_info = QTextEdit()
        self.activation_info.setReadOnly(True)
        self.activation_request_path = None
        load_button = QPushButton("Load .jbsreq")
        load_button.clicked.connect(self._load_activation_request)
        approve_button = QPushButton("Issue .jbsact")
        approve_button.clicked.connect(self._issue_activation)
        layout.addWidget(load_button)
        layout.addWidget(approve_button)
        layout.addWidget(self.activation_info)
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Activation")

    def _build_deactivation_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout()
        self.deactivation_info = QTextEdit()
        self.deactivation_info.setReadOnly(True)
        self.deactivation_request_path = None
        load_button = QPushButton("Load .jbsunreq")
        load_button.clicked.connect(self._load_deactivation_request)
        approve_button = QPushButton("Issue .jbsunact")
        approve_button.clicked.connect(self._issue_deactivation)
        layout.addWidget(load_button)
        layout.addWidget(approve_button)
        layout.addWidget(self.deactivation_info)
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Deactivation")

    def _build_keys_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout()
        generate_button = QPushButton("Generate new key pair")
        generate_button.clicked.connect(self._generate_keys)
        export_button = QPushButton("Export public key")
        export_button.clicked.connect(self._export_public_key)
        load_button = QPushButton("Load private key")
        load_button.clicked.connect(self._load_private_key)
        layout.addWidget(generate_button)
        layout.addWidget(export_button)
        layout.addWidget(load_button)
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Keys")

    # endregion

    # region Helpers
    def _choose_output(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select output", self.output_edit.text())
        if directory:
            self.output_edit.setText(directory)

    def _choose_master(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Select master JBS.exe", str(Path.home()))
        if file_path:
            self.master_binary_edit.setText(file_path)

    def _generate_packages(self) -> None:
        count = self.package_count.value()
        plan = self.plan_combo.currentText()
        max_devices = self.max_devices.value()
        prefix = self.prefix_edit.text()
        output_dir = Path(self.output_edit.text())
        master_binary = Path(self.master_binary_edit.text())
        if not master_binary.exists():
            QMessageBox.warning(self, "Generator", "Master binary not found")
            return
        try:
            packages = self.service.create_license_packages(
                count=count,
                plan=plan,
                max_devices=max_devices,
                output_dir=output_dir,
                prefix=prefix,
                master_binary=master_binary,
            )
        except GeneratorError as exc:
            QMessageBox.critical(self, "Generator", str(exc))
            return
        for package in packages:
            self.log_widget.append(f"Created {package.directory}")
        QMessageBox.information(self, "Generator", f"Created {len(packages)} packages")

    def _load_activation_request(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Load .jbsreq", str(Path.home()), "Activation Request (*.jbsreq)")
        if not file_path:
            return
        request = self.service.load_activation_request(Path(file_path))
        self.activation_request_path = Path(file_path)
        self.activation_info.setPlainText(json.dumps(request.to_dict(), indent=2))

    def _issue_activation(self) -> None:
        if not self.activation_request_path:
            QMessageBox.warning(self, "Generator", "Load a request first")
            return
        request = self.service.load_activation_request(self.activation_request_path)
        try:
            envelope = self.service.issue_activation_response(request)
        except GeneratorError as exc:
            QMessageBox.critical(self, "Generator", str(exc))
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Save .jbsact", str(Path.home()), "Activation Response (*.jbsact)")
        if not file_path:
            return
        Path(file_path).write_text(json.dumps(envelope, indent=2))
        QMessageBox.information(self, "Generator", "Activation issued")

    def _load_deactivation_request(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Load .jbsunreq", str(Path.home()), "Deactivation Request (*.jbsunreq)")
        if not file_path:
            return
        request = self.service.load_deactivation_request(Path(file_path))
        self.deactivation_request_path = Path(file_path)
        self.deactivation_info.setPlainText(json.dumps(request.to_dict(), indent=2))

    def _issue_deactivation(self) -> None:
        if not self.deactivation_request_path:
            QMessageBox.warning(self, "Generator", "Load a request first")
            return
        request = self.service.load_deactivation_request(self.deactivation_request_path)
        try:
            envelope = self.service.issue_deactivation_response(request)
        except GeneratorError as exc:
            QMessageBox.critical(self, "Generator", str(exc))
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Save .jbsunact", str(Path.home()), "Deactivation Response (*.jbsunact)")
        if not file_path:
            return
        Path(file_path).write_text(json.dumps(envelope, indent=2))
        QMessageBox.information(self, "Generator", "Deactivation approved")

    def _generate_keys(self) -> None:
        self.service.private_key_path.unlink(missing_ok=True)
        self.service.public_key_path.unlink(missing_ok=True)
        self.service.ensure_keys()
        QMessageBox.information(self, "Generator", "New RSA key pair generated")

    def _export_public_key(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(self, "Export public.pem", str(Path.home()), "Public Key (*.pem)")
        if not file_path:
            return
        self.service.export_public_key(Path(file_path))
        QMessageBox.information(self, "Generator", "Public key exported")

    def _load_private_key(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Load private.pem", str(Path.home()), "Private Key (*.pem)")
        if not file_path:
            return
        PRIVATE_KEY_PATH.write_bytes(Path(file_path).read_bytes())
        self.service.ensure_keys()
        QMessageBox.information(self, "Generator", "Private key loaded")

    # endregion

    def closeEvent(self, event):  # noqa: N802 - Qt API signature
        self.service.shutdown()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    window = GeneratorWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
