"""Entry point for the JBS client."""
from __future__ import annotations

import sys
from pathlib import Path

from .gui import run_client


def main() -> int:
    public_key_path = Path(__file__).parent / "public.pem"
    return run_client(public_key_path)


if __name__ == "__main__":  # pragma: no cover - manual execution only
    sys.exit(main())
