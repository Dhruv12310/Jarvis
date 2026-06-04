"""The deterministic Tier-0 finance engine. THE defining rule of Phase 4 lives here.

EVERY financial figure is computed by this pure code. The LLM is never imported and never called -
a boundary test enforces it. Money is `Decimal`, so totals are exact and the same inputs always give
the same outputs. Inputs are already-normalized Transactions/Accounts; outputs are Decimals (or
small structs of them). Spending is a POSITIVE magnitude (outflows have negative amounts).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from jarvis.finance.transaction import Account, Budget, BudgetStatus, Recurring, Transaction

_ZERO = Decimal(0)


def _in_range(
    transactions: list[Transaction], start: date | None, end: date | None
) -> list[Transaction]:
    return [
        t
        for t in transactions
        if (start is None or t.date >= start) and (end is None or t.date <= end)
    ]


def total_spending(
    transactions: list[Transaction], start: date | None = None, end: date | None = None
) -> Decimal:
    """Total spent (positive) over the window: the magnitude of all outflows (negative amounts)."""
    return sum((-t.amount for t in _in_range(transactions, start, end) if t.amount < 0), _ZERO)


def spending_by_category(
    transactions: list[Transaction], start: date | None = None, end: date | None = None
) -> dict[str, Decimal]:
    """Spent (positive) per category over the window."""
    totals: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    for t in _in_range(transactions, start, end):
        if t.amount < 0:
            totals[t.category] += -t.amount
    return dict(totals)


def spending_by_period(
    transactions: list[Transaction], period: str = "month"
) -> dict[str, Decimal]:
    """Spent (positive) per period bucket. period = 'month' (YYYY-MM) or 'week' (ISO year-Www)."""
    totals: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    for t in transactions:
        if t.amount < 0:
            totals[_period_key(t.date, period)] += -t.amount
    return dict(totals)


def net_worth(accounts: list[Account]) -> Decimal:
    """Sum of account balances (credit/debt balances are signed by the source)."""
    return sum((a.balance for a in accounts), _ZERO)


def period_over_period(
    transactions: list[Transaction],
    current: tuple[date, date],
    prior: tuple[date, date],
) -> tuple[Decimal, Decimal | None]:
    """(delta, pct) of total spending: current minus prior. pct is None when prior spending is 0."""
    cur = total_spending(transactions, *current)
    pri = total_spending(transactions, *prior)
    delta = cur - pri
    pct = (delta / pri * Decimal(100)) if pri != _ZERO else None
    return delta, pct


def budget_vs_actual(transactions: list[Transaction], budgets: list[Budget]) -> list[BudgetStatus]:
    """Compare each budget's limit to actual category spending over the given transactions."""
    spent = spending_by_category(transactions)
    statuses = []
    for budget in budgets:
        actual = spent.get(budget.category, _ZERO)
        statuses.append(
            BudgetStatus(
                category=budget.category,
                limit=budget.limit,
                actual=actual,
                remaining=budget.limit - actual,
                over=actual > budget.limit,
            )
        )
    return statuses


def recurring_charges(
    transactions: list[Transaction], *, min_occurrences: int = 3
) -> list[Recurring]:
    """Detect subscriptions: a merchant with >= min_occurrences similar-amount regular outflows."""
    by_merchant: dict[str, list[Transaction]] = defaultdict(list)
    for t in transactions:
        if t.amount < 0:
            by_merchant[t.merchant].append(t)

    results = []
    for merchant, txns in by_merchant.items():
        if len(txns) < min_occurrences:
            continue
        txns = sorted(txns, key=lambda t: t.date)
        cadence = _cadence([(b.date - a.date).days for a, b in zip(txns, txns[1:], strict=False)])
        if cadence is None:
            continue
        amounts = sorted(-t.amount for t in txns)
        typical = amounts[len(amounts) // 2]  # median
        if any(abs(a - typical) > typical * Decimal("0.15") for a in amounts):
            continue  # amounts not consistent -> not a fixed subscription
        results.append(
            Recurring(merchant=merchant, amount=typical, count=len(txns), cadence=cadence)
        )
    return results


def _period_key(day: date, period: str) -> str:
    if period == "week":
        iso = day.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return f"{day.year:04d}-{day.month:02d}"  # month


def _cadence(gaps: list[int]) -> str | None:
    if not gaps:
        return None
    avg = sum(gaps) / len(gaps)  # days (not money) - a cadence classification, never a figure
    if 6 <= avg <= 8:
        return "weekly"
    if 13 <= avg <= 16:
        return "biweekly"
    if 26 <= avg <= 33:
        return "monthly"
    return None
