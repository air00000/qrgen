import logging
import sqlite3
from pathlib import Path
from threading import Lock

from app.config import CFG

logger = logging.getLogger(__name__)

_DB_LOCK = Lock()


def _connect() -> sqlite3.Connection:
    db_path = Path(CFG.APP_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def run_migrations() -> None:
    migrations_dir = Path(CFG.BASE_DIR) / "migrations"
    files = sorted(migrations_dir.glob("*.sql"))
    if not files:
        return

    with _DB_LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                  version TEXT PRIMARY KEY,
                  applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            for migration in files:
                version = migration.name
                exists = conn.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = ?", (version,)
                ).fetchone()
                if exists:
                    continue

                sql = migration.read_text(encoding="utf-8")
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_migrations(version) VALUES (?)", (version,)
                )
                logger.info("Applied migration %s", version)
        finally:
            conn.close()


def execute(query: str, params: tuple = ()) -> None:
    with _DB_LOCK:
        conn = _connect()
        try:
            conn.execute(query, params)
        finally:
            conn.close()


def fetchone(query: str, params: tuple = ()):
    with _DB_LOCK:
        conn = _connect()
        try:
            return conn.execute(query, params).fetchone()
        finally:
            conn.close()


def fetchall(query: str, params: tuple = ()):
    with _DB_LOCK:
        conn = _connect()
        try:
            return conn.execute(query, params).fetchall()
        finally:
            conn.close()


def transaction(fn):
    with _DB_LOCK:
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            result = fn(conn)
            conn.execute("COMMIT")
            return result
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
