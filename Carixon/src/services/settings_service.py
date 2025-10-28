from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from ..utils.logger import get_logger
from ..utils.paths import CONFIG_DIR


@dataclass(slots=True)
class Settings:
    language: str
    theme: str
    data: Dict[str, Any]

    def save(self, path: Path) -> None:
        serialized = {"language": self.language, "theme": self.theme, **self.data}
        path.write_text(json.dumps(serialized, indent=2, ensure_ascii=False), encoding="utf-8")


class SettingsService:
    def __init__(self, filename: str = "settings.json") -> None:
        self._path = CONFIG_DIR / filename
        self._logger = get_logger("SettingsService")
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        if not self._path.exists():
            self._logger.info("Creating default settings file at %s", self._path)
            defaults = {
                "language": "cs",
                "theme": "dark",
                "diagnostics_enabled": False,
            }
            self._path.write_text(json.dumps(defaults, indent=2, ensure_ascii=False), encoding="utf-8")

    def load(self) -> Settings:
        data = json.loads(self._path.read_text(encoding="utf-8"))
        language = data.pop("language", "cs")
        theme = data.pop("theme", "dark")
        data.setdefault("diagnostics_enabled", False)
        return Settings(language=language, theme=theme, data=data)

    def update(self, **changes: Any) -> Settings:
        settings = self.load()
        serialized = {"language": settings.language, "theme": settings.theme, **settings.data}
        serialized.update(changes)
        serialized.setdefault("language", settings.language)
        serialized.setdefault("theme", settings.theme)
        self._path.write_text(json.dumps(serialized, indent=2, ensure_ascii=False), encoding="utf-8")
        return self.load()


settings_service = SettingsService()
