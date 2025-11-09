"""SQLite persistence used by the generator application."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from jbs_common.formats import to_iso, utc_now


SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS licenses (
        license_id TEXT PRIMARY KEY,
        plan TEXT NOT NULL,
        issued_utc TEXT NOT NULL,
        expires_utc TEXT,
        max_devices INTEGER NOT NULL,
        note TEXT DEFAULT '',
        archive_prefix TEXT DEFAULT ''
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS activations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_id TEXT NOT NULL REFERENCES licenses(license_id) ON DELETE CASCADE,
        hwid TEXT NOT NULL,
        approved_at_utc TEXT NOT NULL,
        device_index INTEGER NOT NULL,
        UNIQUE(license_id, hwid)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS deactivations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_id TEXT NOT NULL REFERENCES licenses(license_id) ON DELETE CASCADE,
        hwid TEXT NOT NULL,
        approved_at_utc TEXT NOT NULL,
        remark TEXT DEFAULT ''
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_utc TEXT NOT NULL,
        action TEXT NOT NULL,
        details TEXT NOT NULL
    );
    """,
]


@dataclass(slots=True)
class LicenseRecord:
    license_id: str
    plan: str
    issued_utc: str
    expires_utc: Optional[str]
    max_devices: int
    note: str
    archive_prefix: str


class LicenseDatabase:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path)
        self._connection.row_factory = sqlite3.Row
        self._initialise()

    def close(self) -> None:
        self._connection.close()

    def _initialise(self) -> None:
        cur = self._connection.cursor()
        for statement in SCHEMA:
            cur.executescript(statement)
        self._connection.commit()

    @contextmanager
    def cursor(self):
        cur = self._connection.cursor()
        try:
            yield cur
            self._connection.commit()
        finally:
            cur.close()

    def insert_license(self, record: LicenseRecord) -> None:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT OR REPLACE INTO licenses(license_id, plan, issued_utc, expires_utc, max_devices, note, archive_prefix)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.license_id,
                    record.plan,
                    record.issued_utc,
                    record.expires_utc,
                    record.max_devices,
                    record.note,
                    record.archive_prefix,
                ),
            )

    def fetch_license(self, license_id: str) -> Optional[LicenseRecord]:
        cur = self._connection.cursor()
        try:
            row = cur.execute("SELECT * FROM licenses WHERE license_id = ?", (license_id,)).fetchone()
            if not row:
                return None
            return LicenseRecord(
                license_id=row["license_id"],
                plan=row["plan"],
                issued_utc=row["issued_utc"],
                expires_utc=row["expires_utc"],
                max_devices=row["max_devices"],
                note=row["note"],
                archive_prefix=row["archive_prefix"],
            )
        finally:
            cur.close()

    def list_licenses(self) -> List[LicenseRecord]:
        cur = self._connection.cursor()
        try:
            rows = cur.execute("SELECT * FROM licenses ORDER BY issued_utc DESC").fetchall()
            return [
                LicenseRecord(
                    license_id=row["license_id"],
                    plan=row["plan"],
                    issued_utc=row["issued_utc"],
                    expires_utc=row["expires_utc"],
                    max_devices=row["max_devices"],
                    note=row["note"],
                    archive_prefix=row["archive_prefix"],
                )
                for row in rows
            ]
        finally:
            cur.close()

    def record_activation(self, license_id: str, hwid: str, device_index: int) -> None:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT OR IGNORE INTO activations(license_id, hwid, approved_at_utc, device_index)
                VALUES (?, ?, ?, ?)
                """,
                (license_id, hwid, to_iso(utc_now()), device_index),
            )

    def remove_activation(self, license_id: str, hwid: str, remark: str = "") -> None:
        with self.cursor() as cur:
            cur.execute("DELETE FROM activations WHERE license_id = ? AND hwid = ?", (license_id, hwid))
            cur.execute(
                """
                INSERT INTO deactivations(license_id, hwid, approved_at_utc, remark)
                VALUES (?, ?, ?, ?)
                """,
                (license_id, hwid, to_iso(utc_now()), remark),
            )

    def list_activations(self, license_id: str) -> List[sqlite3.Row]:
        cur = self._connection.cursor()
        try:
            return cur.execute(
                "SELECT * FROM activations WHERE license_id = ? ORDER BY device_index ASC",
                (license_id,),
            ).fetchall()
        finally:
            cur.close()

    def add_audit(self, action: str, details: Dict[str, str]) -> None:
        with self.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_log(created_utc, action, details) VALUES (?, ?, ?)",
                (to_iso(utc_now()), action, json.dumps(details, sort_keys=True)),
            )
