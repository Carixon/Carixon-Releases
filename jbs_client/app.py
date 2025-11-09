"""PySide6 based desktop application for the offline JBS client."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from cryptography.hazmat.primitives.asymmetric import rsa

from jbs_client.i18n import TranslationManager
from jbs_client.licensing import LicenseError, LicenseManager
from jbs_common.crypto import load_public_key
from jbs_common.hwid import compute_hwid

CLIENT_VERSION = "1.0.0"


def default_storage_dir() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home()))
    return base / "JBS"


class MainWindow(QMainWindow):
    def __init__(self, manager: LicenseManager, translations: TranslationManager):
        super().__init__()
        self.manager = manager
        self.translations = translations
        self.hwid = compute_hwid()
        self.setWindowTitle(self.translations.translate("app_title"))
        self.resize(600, 400)

        self.status_label = QLabel()
        self.prompt_label = QLabel()
        self.prompt_label.setWordWrap(True)
        self.device_list = QListWidget()

        self.create_req_button = QPushButton()
        self.import_act_button = QPushButton()
        self.create_unreq_button = QPushButton()
        self.import_unact_button = QPushButton()
        self.load_license_button = QPushButton("Load licence")

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addWidget(self.prompt_label)
        layout.addWidget(self.device_list)
        layout.addWidget(self.create_req_button)
        layout.addWidget(self.import_act_button)
        layout.addWidget(self.create_unreq_button)
        layout.addWidget(self.import_unact_button)
        layout.addWidget(self.load_license_button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self._build_menu()
        self._connect_signals()
        self.refresh_texts()
        self._load_existing_license()

    def _build_menu(self) -> None:
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        about_action = QAction(self.translations.translate("menu_about"), self)
        about_action.triggered.connect(self.show_about_dialog)
        toolbar.addAction(about_action)

        language_menu = self.menuBar().addMenu(self.translations.translate("menu_language"))
        for code, locale in self.translations.locales.items():
            action = QAction(locale.name, self)
            action.setCheckable(True)
            action.setChecked(code == self.translations.active_locale)
            action.triggered.connect(lambda checked, c=code: self._change_language(c))
            language_menu.addAction(action)
        self.about_action = about_action
        self.language_menu = language_menu

    def _connect_signals(self) -> None:
        self.create_req_button.clicked.connect(self.handle_create_request)
        self.import_act_button.clicked.connect(self.handle_import_activation)
        self.create_unreq_button.clicked.connect(self.handle_create_deactivation)
        self.import_unact_button.clicked.connect(self.handle_import_deactivation)
        self.load_license_button.clicked.connect(self.handle_load_license)

    # region UI helpers
    def refresh_texts(self) -> None:
        self.setWindowTitle(self.translations.translate("app_title"))
        self.prompt_label.setText(self.translations.translate("activate_prompt"))
        self.create_req_button.setText(self.translations.translate("create_request"))
        self.import_act_button.setText(self.translations.translate("import_response"))
        self.create_unreq_button.setText(self.translations.translate("create_deactivation"))
        self.import_unact_button.setText(self.translations.translate("import_deactivation"))
        self.about_action.setText(self.translations.translate("menu_about"))
        self.language_menu.setTitle(self.translations.translate("menu_language"))
        self.update_status()

    def update_status(self) -> None:
        if not self.manager.license_payload:
            self.status_label.setText(self.translations.translate("status_inactive"))
            self.device_list.clear()
            return
        if self.manager.is_expired():
            self.status_label.setText(self.translations.translate("license_expired"))
        else:
            self.status_label.setText(self.translations.translate("status_active"))
        slots = self.manager.remaining_slots()
        self.prompt_label.setText(
            self.translations.translate("remaining_slots").format(count=slots)
        )
        self.device_list.clear()
        for record in self.manager.activated_devices():
            text = f"HWID: {record.hwid} – {record.approved_at_utc}"
            QListWidgetItem(text, self.device_list)

    def show_about_dialog(self) -> None:
        QMessageBox.information(
            self,
            self.translations.translate("app_title"),
            "\n".join(
                [
                    self.translations.translate("about_author"),
                    self.translations.translate("about_version").format(version=CLIENT_VERSION),
                    f"HWID: {self.hwid}",
                ]
            ),
        )

    # endregion

    # region Handlers
    def _load_existing_license(self) -> None:
        try:
            self.manager.load_existing_license()
        except LicenseError:
            return
        anomaly = self.manager.check_time_anomaly()
        if anomaly:
            QMessageBox.warning(self, "JBS", self.translations.translate("time_rollback"))
        self.update_status()

    def handle_load_license(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Select license", str(Path.home()), "Licence (*.jbslic)")
        if not file_path:
            return
        try:
            self.manager.import_license(Path(file_path))
        except LicenseError as exc:
            QMessageBox.critical(self, "JBS", str(exc))
            return
        self.update_status()

    def handle_create_request(self) -> None:
        if not self.manager.license_payload:
            QMessageBox.warning(self, "JBS", self.translations.translate("status_inactive"))
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Save .jbsreq", str(Path.home()), "Activation Request (*.jbsreq)")
        if not file_path:
            return
        self.manager.export_activation_request(Path(file_path), self.hwid, CLIENT_VERSION, {"hwid": self.hwid})
        QMessageBox.information(self, "JBS", "Activation request created.")

    def handle_import_activation(self) -> None:
        if not self.manager.license_payload:
            QMessageBox.warning(self, "JBS", self.translations.translate("status_inactive"))
            return
        file_path, _ = QFileDialog.getOpenFileName(self, "Import .jbsact", str(Path.home()), "Activation Response (*.jbsact)")
        if not file_path:
            return
        try:
            self.manager.import_activation_file(Path(file_path))
        except LicenseError as exc:
            QMessageBox.critical(self, "JBS", str(exc))
            return
        self.update_status()
        QMessageBox.information(self, "JBS", "Activation successful.")

    def handle_create_deactivation(self) -> None:
        if not self.manager.license_payload:
            QMessageBox.warning(self, "JBS", self.translations.translate("status_inactive"))
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Save .jbsunreq", str(Path.home()), "Deactivation Request (*.jbsunreq)")
        if not file_path:
            return
        selected = self.device_list.currentItem()
        hwid = selected.text().split()[1] if selected else self.hwid
        try:
            self.manager.export_deactivation_request(Path(file_path), hwid, "device replaced")
        except LicenseError as exc:
            QMessageBox.critical(self, "JBS", str(exc))
            return
        QMessageBox.information(self, "JBS", "Deactivation request created.")

    def handle_import_deactivation(self) -> None:
        if not self.manager.license_payload:
            QMessageBox.warning(self, "JBS", self.translations.translate("status_inactive"))
            return
        file_path, _ = QFileDialog.getOpenFileName(self, "Import .jbsunact", str(Path.home()), "Deactivation Response (*.jbsunact)")
        if not file_path:
            return
        try:
            self.manager.import_deactivation_file(Path(file_path))
        except LicenseError as exc:
            QMessageBox.critical(self, "JBS", str(exc))
            return
        self.update_status()
        QMessageBox.information(self, "JBS", "Device slot released.")

    def _change_language(self, code: str) -> None:
        self.translations.set_locale(code)
        for action in self.language_menu.actions():
            action.setChecked(action.text() == self.translations.locales[code].name)
        self.refresh_texts()

    # endregion


def load_public_key_from_bundle() -> rsa.RSAPublicKey:
    bundle_path = Path(__file__).resolve().parent / "public.pem"
    return load_public_key(bundle_path)


def main() -> int:
    app = QApplication(sys.argv)
    translations = TranslationManager(Path(__file__).resolve().parent / "i18n_files")
    public_key = load_public_key_from_bundle()
    manager = LicenseManager(default_storage_dir(), public_key)
    window = MainWindow(manager, translations)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
