from __future__ import annotations

import os
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List

from ..db import models
from ..db.database import session_scope
from ..utils.logger import get_logger
from ..utils.paths import APP_ROOT, BACKUP_DIR, DATA_DIR


@dataclass(slots=True)
class BackupResult:
    path: Path
    size: int
    created_at: datetime


class BackupService:
    def __init__(self) -> None:
        self._logger = get_logger("BackupService")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    def _collect_files(self) -> List[Path]:
        candidates = [DATA_DIR, APP_ROOT / "config", APP_ROOT / "i18n"]
        files: List[Path] = []
        for directory in candidates:
            if not directory.exists():
                continue
            for root, _, filenames in os.walk(directory):
                for name in filenames:
                    files.append(Path(root) / name)
        return files

    def create_backup(self, password: str | None = None) -> BackupResult:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = BACKUP_DIR / f"carixon_backup_{timestamp}.zip"
        files = self._collect_files()
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in files:
                archive.write(file, file.relative_to(APP_ROOT))
            if password:
                archive.setpassword(password.encode("utf-8"))
        size = zip_path.stat().st_size
        with session_scope() as session:
            session.add(models.BackupJob(path=str(zip_path), size=size, success=True))
        self._logger.info("Created backup %s", zip_path)
        return BackupResult(path=zip_path, size=size, created_at=datetime.now())

    def list_backups(self) -> List[BackupResult]:
        results: List[BackupResult] = []
        with session_scope() as session:
            jobs = session.query(models.BackupJob).order_by(models.BackupJob.created_at.desc()).all()
            for job in jobs:
                results.append(
                    BackupResult(
                        path=Path(job.path),
                        size=job.size,
                        created_at=job.created_at,
                    )
                )
        return results


backup_service = BackupService()
