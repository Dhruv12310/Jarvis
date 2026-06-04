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
from jarvis.stores.structured import Goal, Note, StructuredStore

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
            "SELECT id, ts, kind, payload, session_id FROM signals ORDER BY seq DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_signal(row) for row in rows]

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
