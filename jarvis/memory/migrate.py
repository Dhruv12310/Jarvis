"""One-shot migration: move legacy Phase 0 notes into MemoryRecords, then retire the notes table.

Run at startup. Idempotent even under a partial failure: each memory id is derived deterministically
from the note id, so if a crash interrupts the loop before the table is drained, a re-run upserts
the already-copied notes in place (no duplicates) and finishes. Content is re-embedded into the
cosine memory collection (the old Phase 0 ``notes`` vector collection is simply abandoned; SQLite is
the source of truth for the text).
"""

from __future__ import annotations

from jarvis.memory.record import MemoryRecord
from jarvis.memory.store import MemoryStore, default_importance
from jarvis.stores.structured import StructuredStore


def migrate_notes(store: StructuredStore, memory: MemoryStore) -> int:
    """Copy every legacy note into memory and drain the table. Returns the number migrated."""
    notes = store.get_notes(limit=100_000)
    for note in notes:
        memory.save(
            MemoryRecord(
                id=f"note-{note.id}",  # deterministic -> a retry overwrites, never duplicates
                type="observation",
                content=note.content,
                created_at=note.created_at,
                last_accessed_at=note.created_at,
                importance=default_importance(note.content),
                tier="observational",
                confidence=0.6,
                source="interaction",
            )
        )
    if notes:
        store.delete_all_notes()
    return len(notes)
