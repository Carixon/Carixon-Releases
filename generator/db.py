"""SQLite backend for the JBS license generator."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass
class LicenseRow:
    license_id: str
    plan: str
    issued_utc: str
    expires_utc: Optional[str]
    max_devices: int
    note: str
    package_path: Optional[str]


@dataclass
class ActivationRow:
    license_id: str
    hwid: str
    approved_at_utc: str
    device_index: int
    remark: str


class GeneratorDatabase:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._initialise()

    def _initialise(self) -> None:
        cursor = self._conn.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS licenses (
                license_id TEXT PRIMARY KEY,
                plan TEXT NOT NULL,
                issued_utc TEXT NOT NULL,
                expires_utc TEXT,
                max_devices INTEGER NOT NULL,
                note TEXT,
                package_path TEXT
            );

            CREATE TABLE IF NOT EXISTS activations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_id TEXT NOT NULL,
                hwid TEXT NOT NULL,
                approved_at_utc TEXT NOT NULL,
                device_index INTEGER NOT NULL,
                remark TEXT,
                FOREIGN KEY (license_id) REFERENCES licenses(license_id)
            );

            CREATE TABLE IF NOT EXISTS deactivations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_id TEXT NOT NULL,
                hwid TEXT NOT NULL,
                approved_at_utc TEXT NOT NULL,
                remark TEXT,
                FOREIGN KEY (license_id) REFERENCES licenses(license_id)
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                detail TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def transaction(self):
        cursor = self._conn.cursor()
        try:
            yield cursor
        except Exception:
            self._conn.rollback()
            raise
        else:
            self._conn.commit()

    def add_license(self, license_row: LicenseRow) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "INSERT OR REPLACE INTO licenses (license_id, plan, issued_utc, expires_utc, max_devices, note, package_path) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    license_row.license_id,
                    license_row.plan,
                    license_row.issued_utc,
                    license_row.expires_utc,
                    license_row.max_devices,
                    license_row.note,
                    license_row.package_path,
                ),
            )
            self._log(cursor, "LICENSE_CREATED", json.dumps(license_row.__dict__))

    def list_licenses(self) -> List[LicenseRow]:
        cursor = self._conn.cursor()
        rows = cursor.execute("SELECT license_id, plan, issued_utc, expires_utc, max_devices, note, package_path FROM licenses ORDER BY issued_utc DESC").fetchall()
        return [LicenseRow(**dict(row)) for row in rows]

    def get_license(self, license_id: str) -> Optional[LicenseRow]:
        cursor = self._conn.cursor()
        row = cursor.execute(
            "SELECT license_id, plan, issued_utc, expires_utc, max_devices, note, package_path FROM licenses WHERE license_id = ?",
            (license_id,),
        ).fetchone()
        return LicenseRow(**dict(row)) if row else None

    def record_activation(self, activation: ActivationRow) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "INSERT INTO activations (license_id, hwid, approved_at_utc, device_index, remark) VALUES (?, ?, ?, ?, ?)",
                (activation.license_id, activation.hwid, activation.approved_at_utc, activation.device_index, activation.remark),
            )
            self._log(cursor, "ACTIVATION_APPROVED", json.dumps(activation.__dict__))

    def list_activations(self, license_id: str) -> List[ActivationRow]:
        cursor = self._conn.cursor()
        rows = cursor.execute(
            "SELECT license_id, hwid, approved_at_utc, device_index, remark FROM activations WHERE license_id = ? ORDER BY device_index",
            (license_id,),
        ).fetchall()
        return [ActivationRow(**dict(row)) for row in rows]

    def activation_count(self, license_id: str) -> int:
        cursor = self._conn.cursor()
        row = cursor.execute("SELECT COUNT(*) FROM activations WHERE license_id = ?", (license_id,)).fetchone()
        return int(row[0]) if row else 0

    def record_deactivation(self, license_id: str, hwid: str, remark: str) -> None:
        with self.transaction() as cursor:
            cursor.execute(
                "INSERT INTO deactivations (license_id, hwid, approved_at_utc, remark) VALUES (?, ?, ?, ?)",
                (license_id, hwid, datetime.utcnow().isoformat(), remark),
            )
            cursor.execute("DELETE FROM activations WHERE license_id = ? AND hwid = ?", (license_id, hwid))
            self._log(cursor, "DEACTIVATION_APPROVED", json.dumps({"license_id": license_id, "hwid": hwid, "remark": remark}))

    def _log(self, cursor: sqlite3.Cursor, event_type: str, detail: str) -> None:
        cursor.execute(
            "INSERT INTO audit_log (event_type, detail, created_at) VALUES (?, ?, ?)",
            (event_type, detail, datetime.utcnow().isoformat()),
        )

    def list_audit_entries(self) -> Iterable[sqlite3.Row]:
        cursor = self._conn.cursor()
        return cursor.execute("SELECT event_type, detail, created_at FROM audit_log ORDER BY id DESC")


__all__ = ["GeneratorDatabase", "LicenseRow", "ActivationRow"]
