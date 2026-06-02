"""Structured store seam: exact, relational facts.

SQLite is the Phase 0 (and default) backend, kept behind this interface so it stays swappable
(a JSON-tree backend can be validated later; see Core spec section 5.0). Phase 0 implements notes
only. Later phases add domain methods (transactions, goals, calendar events, ...) here without the
business logic ever touching raw SQL.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from jarvis.signals.event import SignalEvent


@dataclass(frozen=True)
class Note:
    id: int
    content: str
    created_at: datetime


class StructuredStore(ABC):
    # notes are legacy: Phase 0 stored memories here, Phase 2 migrates them into MemoryRecords
    # (vector store) and retires the table. These three exist only to seed and drain that migration.
    @abstractmethod
    def save_note(self, content: str) -> Note:
        """Persist a note and return it with its assigned id and creation time."""

    @abstractmethod
    def get_notes(self, limit: int = 50) -> list[Note]:
        """Return the most recent notes, newest first."""

    @abstractmethod
    def delete_all_notes(self) -> None:
        """Drain the legacy notes table (after migrating its rows into MemoryRecords)."""

    @abstractmethod
    def save_signal(self, event: SignalEvent) -> None:
        """Append a signal event to the log (append-only; never updated or deleted)."""

    @abstractmethod
    def get_signals(self, limit: int = 50) -> list[SignalEvent]:
        """Return the most recent signal events, newest first."""
