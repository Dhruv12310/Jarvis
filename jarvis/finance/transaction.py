"""Finance value objects. Money is `decimal.Decimal` (never float) so totals stay exact.

Amounts are signed (OFX convention): negative = outflow/spend, positive = inflow. A transaction `id`
is a deterministic hash of its identifying fields so re-importing an overlapping bank export inserts
each row exactly once.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from jarvis.finance.money import to_cents


@dataclass(frozen=True)
class Transaction:
    id: str
    date: date
    amount: Decimal  # signed: negative = outflow/spend, positive = inflow
    merchant: str
    category: str  # assigned category, or "uncategorized"
    account: str


@dataclass(frozen=True)
class Account:
    id: str
    name: str
    type: str  # checking|savings|credit|...
    balance: Decimal


@dataclass(frozen=True)
class Budget:
    category: str
    limit: Decimal
    period: str  # informational label, e.g. "monthly"


@dataclass(frozen=True)
class BudgetStatus:
    category: str
    limit: Decimal
    actual: Decimal
    remaining: Decimal  # limit - actual (negative when over)
    over: bool


@dataclass(frozen=True)
class Recurring:
    merchant: str
    amount: Decimal  # typical (median) charge
    count: int
    cadence: str  # weekly|biweekly|monthly


def make_id(account: str, txn_date: date, amount: Decimal, merchant: str) -> str:
    """Deterministic id from the identifying fields -> idempotent import (same row -> same id).

    The amount is quantized to cents first, so -12.5 and -12.50 (e.g. from different sources) hash
    to the same id rather than double-counting the same transaction.
    """
    raw = f"{account}|{txn_date.isoformat()}|{to_cents(amount)}|{merchant}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
