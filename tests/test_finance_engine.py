"""The deterministic finance engine vs fixture transactions, with NO LLM. Every figure is exact
Decimal and reproducible - this is the proof that the math path never touches a model.
"""

from datetime import date
from decimal import Decimal

from jarvis.finance import engine
from jarvis.finance.transaction import Account, Budget, Transaction, make_id


def _txn(day, amount, merchant, category, account="chk"):
    amt = Decimal(amount)
    return Transaction(make_id(account, day, amt, merchant), day, amt, merchant, category, account)


# A small fixed ledger: dining + transport outflows in Jan, income, and a Feb dining charge.
LEDGER = [
    _txn(date(2026, 1, 5), "-12.50", "STARBUCKS", "dining"),
    _txn(date(2026, 1, 12), "-30.00", "CHIPOTLE", "dining"),
    _txn(date(2026, 1, 20), "-15.00", "UBER", "transport"),
    _txn(date(2026, 1, 10), "2000.00", "PAYROLL", "income"),
    _txn(date(2026, 2, 3), "-10.00", "STARBUCKS", "dining"),
]


def test_total_spending_is_positive_magnitude_of_outflows():
    # Jan outflows: 12.50 + 30.00 + 15.00 = 57.50 (income excluded).
    assert engine.total_spending(LEDGER, date(2026, 1, 1), date(2026, 1, 31)) == Decimal("57.50")


def test_spending_by_category_groups_outflows():
    result = engine.spending_by_category(LEDGER, date(2026, 1, 1), date(2026, 1, 31))

    assert result == {"dining": Decimal("42.50"), "transport": Decimal("15.00")}
    assert "income" not in result  # inflows are not spending


def test_spending_by_period_buckets_by_month():
    result = engine.spending_by_period(LEDGER, "month")

    assert result == {"2026-01": Decimal("57.50"), "2026-02": Decimal("10.00")}


def test_net_worth_sums_balances():
    accounts = [
        Account("chk", "Checking", "checking", Decimal("1987.50")),
        Account("cc", "Card", "credit", Decimal("-200.25")),
    ]

    assert engine.net_worth(accounts) == Decimal("1787.25")


def test_period_over_period_delta_and_pct():
    # Jan spend 57.50, Feb spend 10.00 -> delta -47.50; pct = -47.50/57.50*100.
    delta, pct = engine.period_over_period(
        LEDGER,
        current=(date(2026, 2, 1), date(2026, 2, 28)),
        prior=(date(2026, 1, 1), date(2026, 1, 31)),
    )

    assert delta == Decimal("-47.50")
    assert pct == (Decimal("-47.50") / Decimal("57.50") * Decimal(100))


def test_period_over_period_pct_is_none_when_prior_is_zero():
    _delta, pct = engine.period_over_period(
        LEDGER,
        current=(date(2026, 1, 1), date(2026, 1, 31)),
        prior=(date(2025, 1, 1), date(2025, 1, 31)),
    )

    assert pct is None  # no division by zero


def test_budget_vs_actual():
    budgets = [
        Budget("dining", Decimal("40.00"), "monthly"),
        Budget("transport", Decimal("50.00"), "monthly"),
    ]
    jan = engine.budget_vs_actual(
        [t for t in LEDGER if t.date.month == 1 and t.date.year == 2026], budgets
    )

    by_cat = {b.category: b for b in jan}
    assert by_cat["dining"].actual == Decimal("42.50")
    assert by_cat["dining"].over is True
    assert by_cat["dining"].remaining == Decimal("-2.50")
    assert by_cat["transport"].over is False
    assert by_cat["transport"].remaining == Decimal("35.00")


def test_recurring_charges_detects_a_monthly_subscription():
    subs = [
        _txn(date(2026, 1, 3), "-9.99", "NETFLIX", "entertainment"),
        _txn(date(2026, 2, 3), "-9.99", "NETFLIX", "entertainment"),
        _txn(date(2026, 3, 3), "-9.99", "NETFLIX", "entertainment"),
        _txn(date(2026, 1, 15), "-4.00", "RANDOM CAFE", "dining"),  # one-off, not recurring
    ]

    recurring = engine.recurring_charges(subs)

    assert len(recurring) == 1
    assert recurring[0].merchant == "NETFLIX"
    assert recurring[0].amount == Decimal("9.99")
    assert recurring[0].cadence == "monthly"
    assert recurring[0].count == 3


def test_engine_is_reproducible():
    # Same inputs -> identical figures, every call (no model, no randomness).
    a = engine.spending_by_category(LEDGER)
    b = engine.spending_by_category(LEDGER)
    assert a == b


def test_all_inflow_ledger_has_zero_spending():
    inflows = [_txn(date(2026, 1, 10), "2000.00", "PAYROLL", "income")]

    assert engine.total_spending(inflows) == Decimal("0")
    assert engine.spending_by_category(inflows) == {}
    assert engine.spending_by_period(inflows) == {}


def test_no_float_drift_in_summation():
    txns = [
        _txn(date(2026, 1, 1), "-0.10", "A", "dining"),
        _txn(date(2026, 1, 2), "-0.20", "B", "dining"),
    ]
    assert engine.total_spending(txns) == Decimal("0.30")  # exact, not 0.30000000000000004


def test_budget_exactly_at_limit_is_not_over():
    txns = [_txn(date(2026, 1, 5), "-40.00", "X", "dining")]
    [status] = engine.budget_vs_actual(txns, [Budget("dining", Decimal("40.00"), "monthly")])

    assert status.over is False  # strict >, so equal is not over
    assert status.remaining == Decimal("0.00")


def test_recurring_rejects_inconsistent_amounts():
    txns = [
        _txn(date(2026, 1, 3), "-9.99", "NETFLIX", "entertainment"),
        _txn(date(2026, 2, 3), "-9.99", "NETFLIX", "entertainment"),
        _txn(date(2026, 3, 3), "-15.00", "NETFLIX", "entertainment"),  # > 15% off the median
    ]
    assert engine.recurring_charges(txns) == []


def test_recurring_rejects_too_few_occurrences():
    txns = [
        _txn(date(2026, 1, 3), "-9.99", "NETFLIX", "entertainment"),
        _txn(date(2026, 2, 3), "-9.99", "NETFLIX", "entertainment"),
    ]
    assert engine.recurring_charges(txns) == []


def test_recurring_detects_weekly_cadence():
    txns = [
        _txn(date(2026, 1, 1), "-5.00", "GYM", "health"),
        _txn(date(2026, 1, 8), "-5.00", "GYM", "health"),
        _txn(date(2026, 1, 15), "-5.00", "GYM", "health"),
    ]
    [recurring] = engine.recurring_charges(txns)
    assert recurring.cadence == "weekly"


def test_spending_by_period_week_bucketing():
    txns = [
        _txn(date(2026, 1, 5), "-10.00", "A", "dining"),  # ISO 2026-W02
        _txn(date(2026, 1, 6), "-5.00", "B", "dining"),  # same week
        _txn(date(2026, 1, 12), "-3.00", "C", "dining"),  # ISO 2026-W03
    ]
    result = engine.spending_by_period(txns, "week")

    assert result == {"2026-W02": Decimal("15.00"), "2026-W03": Decimal("3.00")}
