"""Simple runtime translation management for the JBS client."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


@dataclass(slots=True)
class Locale:
    code: str
    name: str
    translations: Dict[str, str]


class TranslationManager:
    def __init__(self, translations_dir: Path):
        self.translations_dir = translations_dir
        self.locales: Dict[str, Locale] = {}
        self.load_locales()
        self.active_locale = "en"
        if "en" not in self.locales and self.locales:
            self.active_locale = next(iter(self.locales))

    def load_locales(self) -> None:
        for path in self.translations_dir.glob("*.json"):
            data = json.loads(path.read_text())
            self.locales[path.stem] = Locale(code=path.stem, name=data.get("name", path.stem), translations=data.get("strings", {}))

    def set_locale(self, code: str) -> None:
        if code not in self.locales:
            raise KeyError(code)
        self.active_locale = code

    def translate(self, key: str) -> str:
        locale = self.locales.get(self.active_locale)
        if not locale:
            return key
        return locale.translations.get(key, key)
