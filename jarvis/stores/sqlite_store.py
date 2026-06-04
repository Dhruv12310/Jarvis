"""SQLite implementation of StructuredStore.

This is the ONLY module permitted to contain raw SQL. WAL journal mode is enabled so the
always-on Heartbeat (later phases) can read while writers commit; it is cheap and harmless now.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from jarvis.finance.transaction import Account, Budget, Transaction
from jarvis.signals.event import SignalEvent
from jarvis.stores.structured import (
    Goal,
    Note,
    ReflectionState,
    StructuredStore,
    Suggestion,
    Watch,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""

_GOALS_SCHEMA = """
CREATE TABLE IF NOT EXISTS goals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    status      TEXT NOT NULL,
    progress    REAL NOT NULL,
    priority    TEXT NOT NULL,
    deadline    TEXT,
    created_at  TEXT NOT NULL
)
"""

# Append-only event log (Core spec Stage 1). seq gives a reliable newest-first order.
_SIGNALS_SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    id         TEXT NOT NULL,
    ts         TEXT NOT NULL,
    kind       TEXT NOT NULL,
    payload    TEXT NOT NULL,
    session_id TEXT NOT NULL
)
"""

# Finance (Core spec 5.2). Money is stored as TEXT (the exact Decimal string), never REAL/float.
# id is a deterministic hash of the row's identifying fields -> idempotent re-import.
_TRANSACTIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id       TEXT PRIMARY KEY,
    date     TEXT NOT NULL,
    amount   TEXT NOT NULL,
    merchant TEXT NOT NULL,
    category TEXT NOT NULL,
    account  TEXT NOT NULL
)
"""

_ACCOUNTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id      TEXT PRIMARY KEY,
    name    TEXT NOT NULL,
    type    TEXT NOT NULL,
    balance TEXT NOT NULL
)
"""

_BUDGETS_SCHEMA = """
CREATE TABLE IF NOT EXISTS budgets (
    category TEXT PRIMARY KEY,
    amount   TEXT NOT NULL,
    period   TEXT NOT NULL
)
"""

_CATEGORY_OVERRIDES_SCHEMA = """
CREATE TABLE IF NOT EXISTS category_overrides (
    merchant TEXT PRIMARY KEY,
    category TEXT NOT NULL
)
"""

# Reflection baseline (Phase 5 §7.4): one row tracking the last signal seq a reflection processed.
_REFLECTION_STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS reflection_state (
    id                 INTEGER PRIMARY KEY CHECK (id = 1),
    last_seq           INTEGER NOT NULL,
    last_reflection_at TEXT
)
"""

# Materialized user model (Phase 5 §5.3): one row holding the derived parts as JSON; goals are live.
_USER_MODEL_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_model (
    id   INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL
)
"""

# Watchlist (Phase 5b): the user's PUBLIC watch terms - the only terms a collector query may use.
_WATCHLIST_SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
    kind  TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (kind, value)
)
"""

# Surfaced suggestions (Core §5.5). Persisted so 5c can attach Outcomes; json for lists/dicts.
_SUGGESTIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS suggestions (
    id             TEXT PRIMARY KEY,
    created_at     TEXT NOT NULL,
    candidate_type TEXT NOT NULL,
    entity_key     TEXT NOT NULL,
    content        TEXT NOT NULL,
    why            TEXT NOT NULL,
    source_ids     TEXT NOT NULL,
    features       TEXT NOT NULL,
    score          REAL NOT NULL,
    surfaced       INTEGER NOT NULL,
    channel        TEXT NOT NULL
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
        self._conn.execute(_GOALS_SCHEMA)
        self._conn.execute(_SIGNALS_SCHEMA)
        self._conn.execute(_TRANSACTIONS_SCHEMA)
        self._conn.execute(_ACCOUNTS_SCHEMA)
        self._conn.execute(_BUDGETS_SCHEMA)
        self._conn.execute(_CATEGORY_OVERRIDES_SCHEMA)
        self._conn.execute(_REFLECTION_STATE_SCHEMA)
        self._conn.execute(_USER_MODEL_SCHEMA)
        self._conn.execute(_WATCHLIST_SCHEMA)
        self._conn.execute(_SUGGESTIONS_SCHEMA)
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

    def delete_all_notes(self) -> None:
        self._conn.execute("DELETE FROM notes")
        self._conn.commit()

    def save_goal(
        self, description: str, *, priority: str = "medium", deadline: datetime | None = None
    ) -> Goal:
        created_at = datetime.now(UTC)
        cursor = self._conn.execute(
            "INSERT INTO goals (description, status, progress, priority, deadline, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                description,
                "active",
                0.0,
                priority,
                deadline.isoformat() if deadline else None,
                created_at.isoformat(),
            ),
        )
        self._conn.commit()
        return Goal(
            id=cursor.lastrowid,
            description=description,
            status="active",
            progress=0.0,
            priority=priority,
            deadline=deadline,
            created_at=created_at,
        )

    def get_goals(self, status: str | None = None) -> list[Goal]:
        if status is None:
            rows = self._conn.execute(
                "SELECT * FROM goals ORDER BY id DESC",
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM goals WHERE status = ? ORDER BY id DESC",
                (status,),
            ).fetchall()
        return [self._row_to_goal(row) for row in rows]

    def update_goal(
        self, goal_id: int, *, status: str | None = None, progress: float | None = None
    ) -> Goal:
        row = self._conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
        if row is None:
            raise LookupError(f"no goal #{goal_id}")
        updated = replace(
            self._row_to_goal(row),
            status=status if status is not None else row["status"],
            progress=progress if progress is not None else row["progress"],
        )
        self._conn.execute(
            "UPDATE goals SET status = ?, progress = ? WHERE id = ?",
            (updated.status, updated.progress, goal_id),
        )
        self._conn.commit()
        return updated

    def save_transactions(self, transactions: list[Transaction]) -> int:
        # INSERT OR IGNORE dedups on the deterministic id -> re-importing overlap is idempotent.
        before = self._conn.total_changes
        self._conn.executemany(
            "INSERT OR IGNORE INTO transactions (id, date, amount, merchant, category, account) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (t.id, t.date.isoformat(), str(t.amount), t.merchant, t.category, t.account)
                for t in transactions
            ],
        )
        self._conn.commit()
        return self._conn.total_changes - before

    def get_transactions(
        self,
        *,
        start: date | None = None,
        end: date | None = None,
        category: str | None = None,
        account: str | None = None,
    ) -> list[Transaction]:
        clauses, params = [], []
        if start is not None:
            clauses.append("date >= ?")
            params.append(start.isoformat())
        if end is not None:
            clauses.append("date <= ?")
            params.append(end.isoformat())
        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        if account is not None:
            clauses.append("account = ?")
            params.append(account)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM transactions {where} ORDER BY date, id", params
        ).fetchall()
        return [self._row_to_transaction(row) for row in rows]

    def save_account(self, account: Account) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO accounts (id, name, type, balance) VALUES (?, ?, ?, ?)",
            (account.id, account.name, account.type, str(account.balance)),
        )
        self._conn.commit()

    def get_accounts(self) -> list[Account]:
        rows = self._conn.execute("SELECT * FROM accounts ORDER BY id").fetchall()
        return [
            Account(id=r["id"], name=r["name"], type=r["type"], balance=Decimal(r["balance"]))
            for r in rows
        ]

    def save_budget(self, budget: Budget) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO budgets (category, amount, period) VALUES (?, ?, ?)",
            (budget.category, str(budget.limit), budget.period),
        )
        self._conn.commit()

    def get_budgets(self) -> list[Budget]:
        rows = self._conn.execute("SELECT * FROM budgets ORDER BY category").fetchall()
        return [
            Budget(category=r["category"], limit=Decimal(r["amount"]), period=r["period"])
            for r in rows
        ]

    def save_category_override(self, merchant: str, category: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO category_overrides (merchant, category) VALUES (?, ?)",
            (merchant, category),
        )
        self._conn.commit()

    def get_category_overrides(self) -> dict[str, str]:
        rows = self._conn.execute("SELECT merchant, category FROM category_overrides").fetchall()
        return {r["merchant"]: r["category"] for r in rows}

    def recategorize_merchant(self, merchant: str, category: str) -> int:
        cursor = self._conn.execute(
            "UPDATE transactions SET category = ? WHERE merchant = ?", (category, merchant)
        )
        self._conn.commit()
        return cursor.rowcount

    def save_signal(self, event: SignalEvent) -> None:
        self._conn.execute(
            "INSERT INTO signals (id, ts, kind, payload, session_id) VALUES (?, ?, ?, ?, ?)",
            (
                event.id,
                event.ts.isoformat(),
                event.kind,
                json.dumps(event.payload),
                event.session_id,
            ),
        )
        self._conn.commit()

    def get_signals(self, limit: int = 50) -> list[SignalEvent]:
        rows = self._conn.execute(
            "SELECT seq, id, ts, kind, payload, session_id FROM signals ORDER BY seq DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_signal(row) for row in rows]

    def get_signals_since(self, after_seq: int) -> list[SignalEvent]:
        rows = self._conn.execute(
            "SELECT seq, id, ts, kind, payload, session_id FROM signals WHERE seq > ? ORDER BY seq",
            (after_seq,),
        ).fetchall()
        return [self._row_to_signal(row) for row in rows]

    def latest_signal_seq(self) -> int:
        row = self._conn.execute("SELECT MAX(seq) AS m FROM signals").fetchone()
        return row["m"] or 0

    def get_reflection_state(self) -> ReflectionState:
        row = self._conn.execute(
            "SELECT last_seq, last_reflection_at FROM reflection_state WHERE id = 1"
        ).fetchone()
        if row is None:
            return ReflectionState(last_seq=0, last_reflection_at=None)
        at = row["last_reflection_at"]
        return ReflectionState(
            last_seq=row["last_seq"],
            last_reflection_at=datetime.fromisoformat(at) if at else None,
        )

    def save_reflection_state(self, last_seq: int, last_reflection_at: datetime) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO reflection_state (id, last_seq, last_reflection_at) "
            "VALUES (1, ?, ?)",
            (last_seq, last_reflection_at.isoformat()),
        )
        self._conn.commit()

    def get_user_model(self) -> dict:
        row = self._conn.execute("SELECT data FROM user_model WHERE id = 1").fetchone()
        return json.loads(row["data"]) if row else {}

    def save_user_model(self, data: dict) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO user_model (id, data) VALUES (1, ?)", (json.dumps(data),)
        )
        self._conn.commit()

    def clear_user_model(self) -> None:
        self._conn.execute("DELETE FROM user_model")
        self._conn.commit()

    def add_watch(self, kind: str, value: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO watchlist (kind, value) VALUES (?, ?)", (kind, value)
        )
        self._conn.commit()

    def get_watchlist(self) -> list[Watch]:
        rows = self._conn.execute(
            "SELECT kind, value FROM watchlist ORDER BY kind, value"
        ).fetchall()
        return [Watch(kind=row["kind"], value=row["value"]) for row in rows]

    def remove_watch(self, kind: str, value: str) -> None:
        self._conn.execute("DELETE FROM watchlist WHERE kind = ? AND value = ?", (kind, value))
        self._conn.commit()

    def save_suggestion(self, suggestion: Suggestion) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO suggestions (id, created_at, candidate_type, entity_key, "
            "content, why, source_ids, features, score, surfaced, channel) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                suggestion.id,
                suggestion.created_at.isoformat(),
                suggestion.candidate_type,
                suggestion.entity_key,
                suggestion.content,
                suggestion.why,
                json.dumps(suggestion.source_ids),
                json.dumps(suggestion.features),
                suggestion.score,
                int(suggestion.surfaced),
                suggestion.channel,
            ),
        )
        self._conn.commit()

    def get_recent_suggestions(self, *, since: datetime) -> list[Suggestion]:
        rows = self._conn.execute(
            "SELECT * FROM suggestions WHERE created_at >= ? ORDER BY created_at DESC",
            (since.isoformat(),),
        ).fetchall()
        return [self._row_to_suggestion(row) for row in rows]

    @staticmethod
    def _row_to_suggestion(row: sqlite3.Row) -> Suggestion:
        return Suggestion(
            id=row["id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            candidate_type=row["candidate_type"],
            entity_key=row["entity_key"],
            content=row["content"],
            why=row["why"],
            source_ids=json.loads(row["source_ids"]),
            features=json.loads(row["features"]),
            score=row["score"],
            surfaced=bool(row["surfaced"]),
            channel=row["channel"],
        )

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _row_to_signal(row: sqlite3.Row) -> SignalEvent:
        return SignalEvent(
            id=row["id"],
            ts=datetime.fromisoformat(row["ts"]),
            kind=row["kind"],
            payload=json.loads(row["payload"]),
            session_id=row["session_id"],
            seq=row["seq"],
        )

    @staticmethod
    def _row_to_transaction(row: sqlite3.Row) -> Transaction:
        return Transaction(
            id=row["id"],
            date=date.fromisoformat(row["date"]),
            amount=Decimal(row["amount"]),  # exact decimal, never float
            merchant=row["merchant"],
            category=row["category"],
            account=row["account"],
        )

    @staticmethod
    def _row_to_goal(row: sqlite3.Row) -> Goal:
        return Goal(
            id=row["id"],
            description=row["description"],
            status=row["status"],
            progress=row["progress"],
            priority=row["priority"],
            deadline=datetime.fromisoformat(row["deadline"]) if row["deadline"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _row_to_note(row: sqlite3.Row) -> Note:
        return Note(
            id=row["id"],
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
