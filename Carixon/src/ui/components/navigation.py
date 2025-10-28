from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict

from ...i18n.localization import i18n


class Navigation(ttk.Frame):
    def __init__(self, master: tk.Misc, on_select: Callable[[str], None]) -> None:
        super().__init__(master, style="Sidebar.TFrame")
        self._on_select = on_select
        self._buttons: Dict[str, ttk.Button] = {}
        self._create_widgets()

    def _create_widgets(self) -> None:
        sections = [
            ("dashboard", "app.dashboard"),
            ("customers", "app.customers"),
            ("orders", "app.orders"),
            ("invoices", "app.invoices"),
            ("settings", "app.settings"),
        ]
        for index, (key, label_key) in enumerate(sections):
            button = ttk.Button(
                self,
                text=i18n.translate(label_key),
                style="TButton",
                command=lambda value=key: self._on_select(value),
            )
            button.pack(fill="x", padx=16, pady=6)
            self._buttons[key] = button

    def update_labels(self) -> None:
        for key, button in self._buttons.items():
            label_key = f"app.{key}"
            button.config(text=i18n.translate(label_key))
