"""Structured store seam: exact, relational facts.

SQLite is the Phase 0 (and default) backend, kept behind this interface so it stays swappable
(a JSON-tree backend can be validated later; see Core spec section 5.0). Phase 0 implements notes
only. Later phases add domain methods (transactions, goals, calendar events, ...) here without the
business logic ever touching raw SQL.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime

from jarvis.finance.transaction import Account, Budget, Transaction
from jarvis.signals.event import SignalEvent


@dataclass(frozen=True)
class Note:
    id: int
    content: str
    created_at: datetime


@dataclass(frozen=True)
class Goal:
    id: int
    description: str
    status: str  # active|done
    progress: float  # 0.0..1.0
    priority: str  # low|medium|high
    deadline: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class ReflectionState:
    last_seq: int  # signal-log seq processed by the last reflection (monotonic baseline)
    last_reflection_at: datetime | None


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
    def save_goal(
        self, description: str, *, priority: str = "medium", deadline: datetime | None = None
    ) -> Goal:
        """Persist a new active goal (progress 0.0) and return it with its assigned id."""

    @abstractmethod
    def get_goals(self, status: str | None = None) -> list[Goal]:
        """Return goals newest first, optionally filtered by status (active|done)."""

    @abstractmethod
    def update_goal(
        self, goal_id: int, *, status: str | None = None, progress: float | None = None
    ) -> Goal:
        """Set a goal's status and/or progress; return it. Raise LookupError if absent."""

    @abstractmethod
    def save_transactions(self, transactions: list[Transaction]) -> int:
        """Persist transactions idempotently (dedup on id); return the number newly inserted."""

    @abstractmethod
    def get_transactions(
        self,
        *,
        start: date | None = None,
        end: date | None = None,
        category: str | None = None,
        account: str | None = None,
    ) -> list[Transaction]:
        """Return transactions matching the filters, oldest first."""

    @abstractmethod
    def save_account(self, account: Account) -> None:
        """Insert or replace an account (by id)."""

    @abstractmethod
    def get_accounts(self) -> list[Account]:
        """Return all accounts."""

    @abstractmethod
    def save_budget(self, budget: Budget) -> None:
        """Insert or replace a budget (by category)."""

    @abstractmethod
    def get_budgets(self) -> list[Budget]:
        """Return all budgets."""

    @abstractmethod
    def save_category_override(self, merchant: str, category: str) -> None:
        """Persist a user correction: this merchant's category (sticks for future imports)."""

    @abstractmethod
    def get_category_overrides(self) -> dict[str, str]:
        """Return the merchant -> category overrides."""

    @abstractmethod
    def recategorize_merchant(self, merchant: str, category: str) -> int:
        """Set the category of all stored transactions for a merchant; return the count updated."""

    @abstractmethod
    def save_signal(self, event: SignalEvent) -> None:
        """Append a signal event to the log (append-only; never updated or deleted)."""

    @abstractmethod
    def get_signals(self, limit: int = 50) -> list[SignalEvent]:
        """Return the most recent signal events, newest first."""

    @abstractmethod
    def get_signals_since(self, after_seq: int) -> list[SignalEvent]:
        """Return signal events with seq > after_seq, oldest first (the reflection window)."""

    @abstractmethod
    def latest_signal_seq(self) -> int:
        """Return the highest signal seq (0 if empty) - the reflection baseline target."""

    @abstractmethod
    def get_reflection_state(self) -> ReflectionState:
        """Return the reflection baseline (last processed seq + when); seq 0 if never reflected."""

    @abstractmethod
    def save_reflection_state(self, last_seq: int, last_reflection_at: datetime) -> None:
        """Advance the reflection baseline (only after a persisted, successful reflection)."""

    @abstractmethod
    def get_user_model(self) -> dict:
        """Return the materialized user-model derived parts (a JSON dict; {} if none)."""

    @abstractmethod
    def save_user_model(self, data: dict) -> None:
        """Persist the materialized user-model derived parts."""

    @abstractmethod
    def clear_user_model(self) -> None:
        """Wipe the materialized user model (a user-controlled reset)."""
