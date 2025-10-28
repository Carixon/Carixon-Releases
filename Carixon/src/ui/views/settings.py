from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from ...i18n.localization import i18n
from ...services.backup_service import backup_service
from ...services.diagnostics_service import diagnostics_service
from ...services.licensing_service import licensing_service
from ...services.settings_service import settings_service
from ...utils.logger import get_logger
from ..theme.theme_manager import ThemeManager


class SettingsView(ttk.Frame):
    def __init__(self, master: tk.Misc, theme_manager: ThemeManager, on_language_change: Callable[[str], None]) -> None:
        super().__init__(master, padding=24)
        self._theme_manager = theme_manager
        self._on_language_change = on_language_change
        self._logger = get_logger("SettingsView")
        self._language_var = tk.StringVar(value=settings_service.load().language)
        self._theme_var = tk.StringVar(value=theme_manager.active)
        self._diagnostics_var = tk.BooleanVar(value=settings_service.load().data.get("diagnostics_enabled", False))
        self._frames: dict[str, ttk.LabelFrame] = {}
        self._create_layout()
        self._refresh_license()

    def _create_layout(self) -> None:
        for widget in self.winfo_children():
            widget.destroy()
        self._frames.clear()

        language_frame = ttk.LabelFrame(self, text=i18n.translate("settings.language"))
        language_frame.pack(fill="x", pady=12)
        ttk.Combobox(
            language_frame,
            textvariable=self._language_var,
            values=["cs", "en"],
            state="readonly",
        ).pack(fill="x", padx=12, pady=8)
        ttk.Button(language_frame, text=i18n.translate("settings.save"), command=self._save_language).pack(padx=12, pady=(0, 12))
        self._frames["language"] = language_frame

        theme_frame = ttk.LabelFrame(self, text=i18n.translate("settings.theme"))
        theme_frame.pack(fill="x", pady=12)
        ttk.Combobox(
            theme_frame,
            textvariable=self._theme_var,
            values=["dark", "light"],
            state="readonly",
        ).pack(fill="x", padx=12, pady=8)
        ttk.Button(theme_frame, text=i18n.translate("settings.save"), command=self._save_theme).pack(padx=12, pady=(0, 12))
        self._frames["theme"] = theme_frame

        backup_frame = ttk.LabelFrame(self, text=i18n.translate("settings.backup"))
        backup_frame.pack(fill="x", pady=12)
        ttk.Button(backup_frame, text=i18n.translate("settings.backup"), command=self._create_backup).pack(padx=12, pady=8)
        self._frames["backup"] = backup_frame

        license_frame = ttk.LabelFrame(self, text=i18n.translate("settings.license"))
        license_frame.pack(fill="x", pady=12)
        self._license_status = ttk.Label(license_frame, text="")
        self._license_status.pack(fill="x", padx=12, pady=8)
        self._frames["license"] = license_frame

        diagnostics_frame = ttk.LabelFrame(self, text=i18n.translate("settings.diagnostics"))
        diagnostics_frame.pack(fill="x", pady=12)
        ttk.Checkbutton(
            diagnostics_frame,
            text=i18n.translate("settings.diagnostics_label"),
            variable=self._diagnostics_var,
            command=self._toggle_diagnostics,
        ).pack(padx=12, pady=8, anchor="w")
        self._frames["diagnostics"] = diagnostics_frame

    def _save_language(self) -> None:
        language = self._language_var.get()
        settings_service.update(language=language)
        self._on_language_change(language)
        messagebox.showinfo("Carixon", f"Language set to {language}")

    def _save_theme(self) -> None:
        theme = self._theme_var.get()
        self._theme_manager.apply(theme)
        messagebox.showinfo("Carixon", f"Theme changed to {theme}")

    def _create_backup(self) -> None:
        result = backup_service.create_backup()
        messagebox.showinfo("Carixon", f"Backup created: {result.path.name}")

    def _refresh_license(self) -> None:
        status = licensing_service.verify()
        if status.valid:
            remaining = status.remaining_seconds or 0
            days = remaining // 86400
            info = f"License {status.license_id} valid for {days} days"
        else:
            info = f"License invalid: {status.reason}"
        self._license_status.config(text=info)

    def _toggle_diagnostics(self) -> None:
        enabled = self._diagnostics_var.get()
        settings_service.update(diagnostics_enabled=enabled)
        if enabled:
            license_status = licensing_service.verify()
            if license_status.license_id:
                diagnostics_service.enable(license_status.license_id)
        else:
            diagnostics_service.disable()

    def update_language(self) -> None:
        self._create_layout()
        self._refresh_license()
