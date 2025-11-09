"""Entry point for the JBS generator GUI."""
from __future__ import annotations

import sys
from pathlib import Path

from .gui.main import run_gui


def main() -> int:
    database_path = Path.cwd() / "generator.sqlite3"
    return run_gui(database_path)


if __name__ == "__main__":  # pragma: no cover - manual execution only
    sys.exit(main())
