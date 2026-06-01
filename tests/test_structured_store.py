"""StructuredStore (SQLite backend): notes save, fetch newest-first, and persist on disk."""

from datetime import datetime

from jarvis.stores.sqlite_store import SQLiteStructuredStore
from jarvis.stores.structured import Note


def test_save_note_returns_note_with_id_and_timestamp(tmp_path):
    store = SQLiteStructuredStore(tmp_path / "jarvis.db")

    note = store.save_note("buy milk")

    assert isinstance(note, Note)
    assert note.id >= 1
    assert note.content == "buy milk"
    assert isinstance(note.created_at, datetime)


def test_get_notes_returns_saved_notes_newest_first(tmp_path):
    store = SQLiteStructuredStore(tmp_path / "jarvis.db")
    store.save_note("first")
    store.save_note("second")

    assert [n.content for n in store.get_notes()] == ["second", "first"]


def test_get_notes_respects_limit(tmp_path):
    store = SQLiteStructuredStore(tmp_path / "jarvis.db")
    for i in range(5):
        store.save_note(f"note {i}")

    assert len(store.get_notes(limit=3)) == 3


def test_get_notes_is_empty_on_a_fresh_store(tmp_path):
    store = SQLiteStructuredStore(tmp_path / "jarvis.db")

    assert store.get_notes() == []


def test_notes_persist_across_store_instances(tmp_path):
    path = tmp_path / "jarvis.db"
    first = SQLiteStructuredStore(path)
    first.save_note("durable")
    first.close()

    second = SQLiteStructuredStore(path)

    assert [n.content for n in second.get_notes()] == ["durable"]


def test_wal_journal_mode_is_enabled(tmp_path):
    store = SQLiteStructuredStore(tmp_path / "jarvis.db")

    mode = store._conn.execute("PRAGMA journal_mode").fetchone()[0]

    assert mode.lower() == "wal"
