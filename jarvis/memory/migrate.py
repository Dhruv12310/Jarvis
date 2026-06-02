"""One-shot migration: move legacy Phase 0 notes into MemoryRecords, then retire the notes table.

Run at startup. Idempotent: it drains the notes table once the rows are copied, so a second run
finds nothing to move. Content is re-embedded into the cosine memory collection (the old Phase 0
``notes`` vector collection is simply abandoned; SQLite is the source of truth for the text).
"""

from __future__ import annotations

from uuid import uuid4

from jarvis.memory.record import MemoryRecord
from jarvis.memory.store import MemoryStore, default_importance
from jarvis.stores.structured import StructuredStore


def migrate_notes(store: StructuredStore, memory: MemoryStore) -> int:
    """Copy every legacy note into memory and drain the table. Returns the number migrated."""
    notes = store.get_notes(limit=100_000)
    for note in notes:
        memory.save(
            MemoryRecord(
                id=uuid4().hex,
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
