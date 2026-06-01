"""SQLite implementation of StructuredStore.

This is the ONLY module permitted to contain raw SQL. WAL journal mode is enabled so the
always-on Heartbeat (later phases) can read while writers commit; it is cheap and harmless now.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from jarvis.stores.structured import Note, StructuredStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


class SQLiteStructuredStore(StructuredStore):
    def __init__(self, db_path: Path | str) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def save_note(self, content: str) -> Note:
        created_at = datetime.now(UTC)
        cursor = self._conn.execute(
            "INSERT INTO notes (content, created_at) VALUES (?, ?)",
            (content, created_at.isoformat()),
        )
        self._conn.commit()
        return Note(id=cursor.lastrowid, content=content, created_at=created_at)

    def get_notes(self, limit: int = 50) -> list[Note]:
        rows = self._conn.execute(
            "SELECT id, content, created_at FROM notes ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_note(row) for row in rows]

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _row_to_note(row: sqlite3.Row) -> Note:
        return Note(
            id=row["id"],
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
