"""PySide6 GUI for the JBS offline client."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QComboBox,
)

from .licensing import LicenseManager, TimeRollbackDetected
from .localization import LocalizationManager


class WizardWidget(QWidget):
    def __init__(self, license_manager: LicenseManager, i18n: LocalizationManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.license_manager = license_manager
        self.i18n = i18n
        layout = QVBoxLayout(self)

        self.title = QLabel(self.i18n.translate("wizard.title"))
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self.title)

        self.description = QLabel(self.i18n.translate("wizard.description"))
        self.description.setWordWrap(True)
        layout.addWidget(self.description)

        button_layout = QHBoxLayout()
        self.create_request_btn = QPushButton(self.i18n.translate("wizard.create_request"))
        self.create_request_btn.clicked.connect(self._create_request)
        button_layout.addWidget(self.create_request_btn)

        self.import_activation_btn = QPushButton(self.i18n.translate("wizard.import_activation"))
        self.import_activation_btn.clicked.connect(self._import_activation)
        button_layout.addWidget(self.import_activation_btn)

        layout.addLayout(button_layout)
        layout.addStretch()

    def _create_request(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(self, "Create activation request", "activation_request")
        if not filename:
            return
        try:
            self.license_manager.create_activation_request(Path(filename))
        except Exception as exc:  # pragma: no cover - UI feedback only
            QMessageBox.critical(self, "Error", str(exc))
        else:  # pragma: no cover - UI feedback only
            QMessageBox.information(self, "Activation request", "Request file created successfully.")

    def _import_activation(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Import activation response", filter="Activation (*.jbsact)")
        if not filename:
            return
        try:
            record = self.license_manager.import_activation_response(Path(filename))
        except Exception as exc:  # pragma: no cover - UI feedback only
            QMessageBox.critical(self, "Error", str(exc))
        else:  # pragma: no cover - UI feedback only
            QMessageBox.information(self, "Activation", f"Activation for HWID {record.hwid} imported.")
            self.parent().refresh()  # type: ignore[attr-defined]


class LicenseOverviewWidget(QWidget):
    def __init__(self, license_manager: LicenseManager, i18n: LocalizationManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.license_manager = license_manager
        self.i18n = i18n
        self.layout = QVBoxLayout(self)

        self.status_label = QLabel()
        self.layout.addWidget(self.status_label)

        self.details_label = QLabel()
        self.layout.addWidget(self.details_label)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["HWID", "Approved", "Index"])
        self.layout.addWidget(self.table)

        buttons_layout = QHBoxLayout()
        self.deactivation_request_btn = QPushButton(self.i18n.translate("license.create_deactivation"))
        self.deactivation_request_btn.clicked.connect(self._create_deactivation)
        buttons_layout.addWidget(self.deactivation_request_btn)

        self.deactivation_import_btn = QPushButton(self.i18n.translate("license.import_deactivation"))
        self.deactivation_import_btn.clicked.connect(self._import_deactivation)
        buttons_layout.addWidget(self.deactivation_import_btn)

        self.layout.addLayout(buttons_layout)
        self.refresh()

    def refresh(self) -> None:
        if not self.license_manager.license:
            self.status_label.setText(self.i18n.translate("license.status_inactive"))
            return
        license_ = self.license_manager.license
        status = self.i18n.translate("license.status_active") if self.license_manager.is_device_authorized() else self.i18n.translate("license.status_inactive")
        self.status_label.setText(status)
        expires = license_.expires_utc.isoformat() if license_.expires_utc else "∞"
        details = f"{self.i18n.translate('license.plan')}: {license_.plan}\n{self.i18n.translate('license.expires')}: {expires}\n{self.i18n.translate('license.max_devices')}: {license_.max_devices}"
        self.details_label.setText(details)

        self.table.setRowCount(0)
        for record in self.license_manager.activation_state.devices:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(record.hwid))
            self.table.setItem(row, 1, QTableWidgetItem(record.approved_at_utc.isoformat()))
            self.table.setItem(row, 2, QTableWidgetItem(str(record.device_index)))

    def _create_deactivation(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(self, "Create deactivation request", "deactivation_request")
        if not filename:
            return
        try:
            self.license_manager.create_deactivation_request(Path(filename))
        except Exception as exc:  # pragma: no cover - UI feedback only
            QMessageBox.critical(self, "Error", str(exc))
        else:  # pragma: no cover - UI feedback only
            QMessageBox.information(self, "Deactivation request", "Request created successfully.")

    def _import_deactivation(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Import deactivation response", filter="Deactivation (*.jbsunact)")
        if not filename:
            return
        try:
            self.license_manager.import_deactivation_response(Path(filename))
        except Exception as exc:  # pragma: no cover - UI feedback only
            QMessageBox.critical(self, "Error", str(exc))
        else:  # pragma: no cover - UI feedback only
            QMessageBox.information(self, "Deactivation", "Deactivation processed successfully.")
            self.refresh()


class MainWindow(QMainWindow):
    def __init__(self, license_manager: LicenseManager, i18n: LocalizationManager) -> None:
        super().__init__()
        self.license_manager = license_manager
        self.i18n = i18n
        self.setWindowTitle(self.i18n.translate("app.title"))

        self.content_widget = QWidget()
        self.setCentralWidget(self.content_widget)
        self.layout = QVBoxLayout(self.content_widget)

        self.language_selector = QComboBox()
        self.language_selector.addItems(sorted(self.i18n.available_languages().keys()))
        self.language_selector.currentTextChanged.connect(self._change_language)
        self.layout.addWidget(self.language_selector)

        self.wizard_widget = WizardWidget(self.license_manager, self.i18n, self)
        self.overview_widget = LicenseOverviewWidget(self.license_manager, self.i18n, self)

        self.layout.addWidget(self.wizard_widget)
        self.layout.addWidget(self.overview_widget)

        self._create_menu()

    def _create_menu(self) -> None:
        about_action = QAction(self.i18n.translate("menu.about"), self)
        about_action.triggered.connect(self._show_about)
        self.menuBar().addAction(about_action)

    def _show_about(self) -> None:  # pragma: no cover - GUI only
        QMessageBox.information(
            self,
            self.i18n.translate("about.title"),
            f"JBS – Just Be Safe\n{self.i18n.translate('about.author')}\n{self.i18n.translate('about.version')}: 1.0",
        )

    def refresh(self) -> None:
        self.overview_widget.refresh()

    def _change_language(self, language: str) -> None:
        try:
            self.i18n.set_language(language)
        except KeyError:
            return
        self.setWindowTitle(self.i18n.translate("app.title"))
        self.wizard_widget.title.setText(self.i18n.translate("wizard.title"))
        self.wizard_widget.description.setText(self.i18n.translate("wizard.description"))
        self.wizard_widget.create_request_btn.setText(self.i18n.translate("wizard.create_request"))
        self.wizard_widget.import_activation_btn.setText(self.i18n.translate("wizard.import_activation"))
        self.overview_widget.deactivation_request_btn.setText(self.i18n.translate("license.create_deactivation"))
        self.overview_widget.deactivation_import_btn.setText(self.i18n.translate("license.import_deactivation"))
        self.overview_widget.refresh()


def run_client(public_key_path: Path) -> int:
    app = QApplication(sys.argv)
    i18n = LocalizationManager(Path(__file__).parent / "i18n")
    public_key_pem = public_key_path.read_bytes()
    manager = LicenseManager(public_key_pem)
    try:
        manager.load()
    except FileNotFoundError as exc:
        QMessageBox.critical(None, "License", str(exc))
        return 1
    except TimeRollbackDetected as exc:
        QMessageBox.critical(None, "Clock", str(exc))
        return 2
    window = MainWindow(manager, i18n)
    window.show()
    return app.exec()


__all__ = ["run_client", "MainWindow"]
