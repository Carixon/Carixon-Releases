from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from ..utils.logger import get_logger
from ..utils.paths import CONFIG_DIR, I18N_DIR


class LocalizationManager:
    def __init__(self) -> None:
        self._translations: Dict[str, Dict[str, str]] = {}
        self._language = "cs"
        self._logger = get_logger("Localization")
        self._load_translations()
        self._load_language_override()

    def _load_translations(self) -> None:
        default_files = {
            "cs": I18N_DIR / "cs.json",
            "en": I18N_DIR / "en.json",
        }
        for lang, path in default_files.items():
            if not path.exists():
                self._logger.warning("Translation file %s not found, creating fallback.", path)
                path.write_text(json.dumps({"app.title": "Carixon"}, ensure_ascii=False, indent=2), encoding="utf-8")
            with path.open(encoding="utf-8") as fh:
                self._translations[lang] = json.load(fh)

    def _load_language_override(self) -> None:
        settings_file = CONFIG_DIR / "settings.json"
        if settings_file.exists():
            try:
                data = json.loads(settings_file.read_text(encoding="utf-8"))
                self._language = data.get("language", "cs")
            except json.JSONDecodeError:
                self._logger.exception("Failed to read settings.json, defaulting language to CS.")

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, language: str) -> None:
        if language not in self._translations:
            raise ValueError(f"Unsupported language: {language}")
        self._language = language
        settings_file = CONFIG_DIR / "settings.json"
        if settings_file.exists():
            data = json.loads(settings_file.read_text(encoding="utf-8"))
        else:
            data = {}
        data["language"] = language
        settings_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def translate(self, key: str, **kwargs: str) -> str:
        catalog = self._translations.get(self._language, {})
        template = catalog.get(key, key)
        return template.format(**kwargs)


i18n = LocalizationManager()
