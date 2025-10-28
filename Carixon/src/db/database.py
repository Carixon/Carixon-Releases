from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator

from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..utils.logger import get_logger
from ..utils.paths import DATA_DIR


LOGGER = get_logger("Database")


class Base(DeclarativeBase):
    pass


def _create_engine() -> Engine:
    db_path = DATA_DIR / "carixon.db"
    from sqlalchemy import create_engine

    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}, future=True, echo=False
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # type: ignore[override]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


ENGINE = _create_engine()
SessionLocal = sessionmaker(bind=ENGINE, class_=Session, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:  # pragma: no cover - defensive
        session.rollback()
        LOGGER.exception("Database error, transaction rolled back.")
        raise
    finally:
        session.close()


def init_db() -> None:
    from . import models  # noqa: WPS433 - import to register models

    Base.metadata.create_all(bind=ENGINE)

    # Configure FTS virtual tables
    with ENGINE.connect() as conn:
        conn.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS customers_fts USING fts5(
                    customer_id UNINDEXED,
                    full_name,
                    email,
                    phone,
                    notes,
                    content='customers',
                    content_rowid='id'
                )
                """
            )
        )
        conn.commit()

        conn.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS customers_ai AFTER INSERT ON customers BEGIN
                    INSERT INTO customers_fts(rowid, customer_id, full_name, email, phone, notes)
                    VALUES (new.id, new.id, new.first_name || ' ' || new.last_name, new.email, new.phone, new.notes);
                END;
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS customers_ad AFTER DELETE ON customers BEGIN
                    INSERT INTO customers_fts(customers_fts, rowid, customer_id, full_name, email, phone, notes)
                    VALUES('delete', old.id, old.id, old.first_name || ' ' || old.last_name, old.email, old.phone, old.notes);
                END;
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS customers_au AFTER UPDATE ON customers BEGIN
                    INSERT INTO customers_fts(customers_fts, rowid, customer_id, full_name, email, phone, notes)
                    VALUES('delete', old.id, old.id, old.first_name || ' ' || old.last_name, old.email, old.phone, old.notes);
                    INSERT INTO customers_fts(rowid, customer_id, full_name, email, phone, notes)
                    VALUES (new.id, new.id, new.first_name || ' ' || new.last_name, new.email, new.phone, new.notes);
                END;
                """
            )
        )
        conn.commit()


init_db()
