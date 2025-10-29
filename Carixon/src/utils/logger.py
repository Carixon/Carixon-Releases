from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from .paths import LOGS_DIR


_LOGGER: Optional[logging.Logger] = None


def get_logger(name: str = "carixon") -> logging.Logger:
    global _LOGGER
    if _LOGGER is None:
        LOGS_DIR.mkdir(exist_ok=True, parents=True)
        log_file = LOGS_DIR / "carixon.log"
        handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")
        handler.setFormatter(formatter)

        console = logging.StreamHandler()
        console.setFormatter(formatter)

        _LOGGER = logging.getLogger("carixon")
        _LOGGER.setLevel(logging.INFO)
        _LOGGER.addHandler(handler)
        _LOGGER.addHandler(console)
    return _LOGGER.getChild(name)


def enable_debug_mode() -> None:
    logger = get_logger()
    logger.setLevel(logging.DEBUG)
    for handler in logger.handlers:
        handler.setLevel(logging.DEBUG)
