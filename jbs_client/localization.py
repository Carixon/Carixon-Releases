"""Runtime localization helper for the JBS client."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


class LocalizationManager:
    def __init__(self, translations_path: Path) -> None:
        self.translations_path = translations_path
        self._translations: Dict[str, Dict[str, str]] = {}
        self._current_language = "en"
        self.load_all()

    def load_all(self) -> None:
        for file in self.translations_path.glob("*.json"):
            language = file.stem
            self._translations[language] = json.loads(file.read_text(encoding="utf-8"))

    def available_languages(self) -> Dict[str, Dict[str, str]]:
        return self._translations

    def set_language(self, language: str) -> None:
        if language not in self._translations:
            raise KeyError(f"Unknown language: {language}")
        self._current_language = language

    def translate(self, key: str) -> str:
        return self._translations.get(self._current_language, {}).get(key, key)


__all__ = ["LocalizationManager"]
