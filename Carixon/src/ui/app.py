from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict

from ..i18n.localization import i18n
from ..services.licensing_service import licensing_service
from ..services.sync_service import sync_service
from ..utils.logger import get_logger
from .components.navigation import Navigation
from .theme.theme_manager import ThemeManager
from .views.customers import CustomerView
from .views.dashboard import DashboardView
from .views.invoices import InvoicesView
from .views.orders import OrdersView
from .views.settings import SettingsView


class CarixonApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self._logger = get_logger("App")
        self.title(i18n.translate("app.title"))
        self.geometry("1280x800")
        self.minsize(1024, 720)
        self._theme_manager = ThemeManager(self)
        self._views: Dict[str, ttk.Frame] = {}
        self._content_frame = ttk.Frame(self)
        self._content_frame.pack(fill="both", expand=True)
        self._navigation = Navigation(self._content_frame, self.show_view)
        self._navigation.pack(side="left", fill="y")
        self._view_container = ttk.Frame(self._content_frame, style="TFrame")
        self._view_container.pack(side="left", fill="both", expand=True)
        self._create_views()
        self._verify_license()
        self.show_view("dashboard")
        self._schedule_notifications()

    def _create_views(self) -> None:
        self._views["dashboard"] = DashboardView(self._view_container)
        self._views["customers"] = CustomerView(self._view_container)
        self._views["orders"] = OrdersView(self._view_container)
        self._views["invoices"] = InvoicesView(self._view_container)
        self._views["settings"] = SettingsView(self._view_container, self._theme_manager, self.change_language)
        for view in self._views.values():
            view.pack_forget()

    def show_view(self, key: str) -> None:
        view = self._views.get(key)
        if not view:
            return
        for widget in self._view_container.winfo_children():
            widget.pack_forget()
        view.pack(fill="both", expand=True)
        if hasattr(view, "refresh"):
            view.refresh()  # type: ignore[attr-defined]

    def change_language(self, language: str) -> None:
        try:
            i18n.set_language(language)
        except ValueError as exc:
            messagebox.showerror("Carixon", str(exc))
            return
        self.title(i18n.translate("app.title"))
        self._navigation.update_labels()
        for view in self._views.values():
            if hasattr(view, "update_language"):
                view.update_language()  # type: ignore[attr-defined]

    def _verify_license(self) -> None:
        status = licensing_service.verify()
        if not status.valid:
            messagebox.showerror("Carixon", f"License error: {status.reason}")
        else:
            days = (status.remaining_seconds or 0) // 86400
            self._logger.info("License valid for %s days", days)

    def _schedule_notifications(self) -> None:
        def refresh_notifications() -> None:
            try:
                sync_service.fetch_carixon_alerts()
            except Exception:
                self._logger.debug("Failed to fetch Carixon alerts", exc_info=True)
            try:
                sync_service.fetch_google_script_notifications()
            except Exception:
                self._logger.debug("Failed to fetch Google notifications", exc_info=True)
            dashboard = self._views.get("dashboard")
            if dashboard and hasattr(dashboard, "refresh"):
                dashboard.refresh()  # type: ignore[attr-defined]
            self.after(60000, refresh_notifications)

        self.after(1000, refresh_notifications)


__all__ = ["CarixonApp"]
