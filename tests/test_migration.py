"""Phase 0 -> Phase 2 notes migration: legacy notes become MemoryRecords, then the table is drained.

Clean (no orphans) and idempotent (a second run finds nothing to move).
"""

from jarvis.memory.migrate import migrate_notes
from jarvis.memory.store import MemoryStore
from jarvis.stores.sqlite_store import SQLiteStructuredStore
from tests.test_memory_store import _FakeVector


def _backends(tmp_path, fake_embedder):
    store = SQLiteStructuredStore(tmp_path / "jarvis.db")
    memory = MemoryStore(_FakeVector(), fake_embedder)
    return store, memory


def test_migration_moves_notes_into_memory(tmp_path, fake_embedder):
    store, memory = _backends(tmp_path, fake_embedder)
    store.save_note("dentist appointment friday")
    store.save_note("buy groceries")

    moved = migrate_notes(store, memory)

    assert moved == 2
    assert sorted(r.content for r in memory.all()) == [
        "buy groceries",
        "dentist appointment friday",
    ]


def test_migration_drains_the_notes_table(tmp_path, fake_embedder):
    store, memory = _backends(tmp_path, fake_embedder)
    store.save_note("old note")

    migrate_notes(store, memory)

    assert store.get_notes() == []  # no orphans left behind


def test_migration_is_idempotent(tmp_path, fake_embedder):
    store, memory = _backends(tmp_path, fake_embedder)
    store.save_note("only once")

    assert migrate_notes(store, memory) == 1
    assert migrate_notes(store, memory) == 0  # nothing left to move
    assert len(memory.all()) == 1  # not duplicated


def test_migration_preserves_creation_time(tmp_path, fake_embedder):
    store, memory = _backends(tmp_path, fake_embedder)
    note = store.save_note("timestamped")

    migrate_notes(store, memory)

    assert memory.all()[0].created_at == note.created_at


def test_migration_on_empty_store_is_a_noop(tmp_path, fake_embedder):
    store, memory = _backends(tmp_path, fake_embedder)

    assert migrate_notes(store, memory) == 0
    assert memory.all() == []


def test_migration_is_idempotent_after_a_partial_failure(tmp_path, fake_embedder):
    # An embedder that fails on the 2nd save aborts the first run mid-loop (table not drained).
    # Because each memory id is derived from the note id, the retry overwrites rather than dupes.
    store, memory = _backends(tmp_path, fake_embedder)
    store.save_note("alpha")
    store.save_note("beta")
    store.save_note("gamma")

    calls = {"n": 0}
    real_embed = fake_embedder.embed

    def flaky(text):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("embedder hiccup")
        return real_embed(text)

    fake_embedder.embed = flaky
    try:
        migrate_notes(store, memory)  # crashes partway, notes NOT drained
    except RuntimeError:
        pass
    fake_embedder.embed = real_embed

    migrate_notes(store, memory)  # clean re-run

    assert sorted(r.content for r in memory.all()) == ["alpha", "beta", "gamma"]  # no duplicates
    assert store.get_notes() == []
