from __future__ import annotations

from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = APP_ROOT / "data"
BACKUP_DIR = APP_ROOT / "backup"
CONFIG_DIR = APP_ROOT / "config"
ASSETS_DIR = APP_ROOT / "assets"
I18N_DIR = APP_ROOT / "i18n"
LOGS_DIR = APP_ROOT / "logs"


for directory in (DATA_DIR, BACKUP_DIR, CONFIG_DIR, ASSETS_DIR, I18N_DIR, LOGS_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def customer_folder(customer_id: int, display_name: str) -> Path:
    safe_name = "_".join(display_name.split()) or str(customer_id)
    folder = DATA_DIR / "customers" / f"{customer_id}_{safe_name}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder
