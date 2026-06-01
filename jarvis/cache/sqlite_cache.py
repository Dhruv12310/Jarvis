"""SQLite implementation of Cache.

One of the two modules permitted to contain raw SQL (alongside ``stores/sqlite_store.py``). WAL mode
is enabled, matching the structured store.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jarvis.cache.base import Cache

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    expires_at TEXT NOT NULL
)
"""


class SQLiteCache(Cache):
    def __init__(self, db_path: Path | str) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def get(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value, expires_at FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        value, expires_at = row
        if datetime.fromisoformat(expires_at) <= datetime.now(UTC):
            self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            self._conn.commit()
            return None
        return value

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        expires_at = (datetime.now(UTC) + timedelta(seconds=ttl_seconds)).isoformat()
        self._conn.execute(
            "INSERT INTO cache (key, value, expires_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET "
            "value = excluded.value, expires_at = excluded.expires_at",
            (key, value, expires_at),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
