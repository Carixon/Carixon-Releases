from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import tkinter as tk
from tkinter import ttk

from ...services.settings_service import settings_service
from ...utils.logger import get_logger


@dataclass(slots=True)
class Theme:
    name: str
    colors: Dict[str, str]


class ThemeManager:
    def __init__(self, root: tk.Misc) -> None:
        self._root = root
        self._style = ttk.Style(root)
        self._logger = get_logger("ThemeManager")
        self._themes = self._create_themes()
        self._active = settings_service.load().theme
        self.apply(self._active)

    def _create_themes(self) -> Dict[str, Theme]:
        return {
            "dark": Theme(
                name="dark",
                colors={
                    "background": "#1e1e2f",
                    "surface": "#2d2d40",
                    "accent": "#5f9ea0",
                    "text": "#f8f8f2",
                },
            ),
            "light": Theme(
                name="light",
                colors={
                    "background": "#f4f4f6",
                    "surface": "#ffffff",
                    "accent": "#3f51b5",
                    "text": "#1f1f1f",
                },
            ),
        }

    @property
    def active(self) -> str:
        return self._active

    def apply(self, name: str) -> None:
        theme = self._themes.get(name, self._themes["dark"])
        self._active = theme.name
        self._style.theme_use("clam")
        self._style.configure(
            "TFrame",
            background=theme.colors["background"],
        )
        self._style.configure(
            "Card.TFrame",
            background=theme.colors["surface"],
            borderwidth=0,
        )
        self._style.configure(
            "Accent.TButton",
            background=theme.colors["accent"],
            foreground=theme.colors["text"],
            relief="flat",
        )
        self._style.configure(
            "TButton",
            background=theme.colors["surface"],
            foreground=theme.colors["text"],
            borderwidth=0,
        )
        self._style.configure(
            "Sidebar.TFrame",
            background=theme.colors["surface"],
        )
        self._root.configure(bg=theme.colors["background"])
        settings_service.update(theme=theme.name)
        self._logger.info("Applied theme %s", theme.name)


__all__ = ["ThemeManager"]
