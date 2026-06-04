"""Finance store: Decimal round-trip, idempotent re-import, filtered queries, accounts (temp DB)."""

from datetime import date
from decimal import Decimal

from jarvis.finance.transaction import Account, Transaction, make_id
from jarvis.stores.sqlite_store import SQLiteStructuredStore


def _txn(day, amount, merchant, *, category="uncategorized", account="chk"):
    return Transaction(
        id=make_id(account, day, Decimal(amount), merchant),
        date=day,
        amount=Decimal(amount),
        merchant=merchant,
        category=category,
        account=account,
    )


def test_transactions_round_trip_with_exact_decimal(tmp_path):
    store = SQLiteStructuredStore(tmp_path / "j.db")

    added = store.save_transactions([_txn(date(2026, 1, 5), "-12.50", "STARBUCKS")])

    assert added == 1
    [txn] = store.get_transactions()
    assert txn.amount == Decimal("-12.50")  # exact, not 12.5 float drift
    assert txn.merchant == "STARBUCKS"
    assert txn.date == date(2026, 1, 5)


def test_reimport_is_idempotent(tmp_path):
    store = SQLiteStructuredStore(tmp_path / "j.db")
    txns = [_txn(date(2026, 1, 5), "-12.50", "A"), _txn(date(2026, 1, 6), "-3.00", "B")]

    assert store.save_transactions(txns) == 2
    assert store.save_transactions(txns) == 0  # re-importing the same rows inserts nothing
    assert len(store.get_transactions()) == 2


def test_get_transactions_filters(tmp_path):
    store = SQLiteStructuredStore(tmp_path / "j.db")
    store.save_transactions(
        [
            _txn(date(2026, 1, 5), "-12.50", "A", category="dining"),
            _txn(date(2026, 2, 1), "-3.00", "B", category="transport", account="cc"),
        ]
    )

    assert len(store.get_transactions(start=date(2026, 1, 1), end=date(2026, 1, 31))) == 1
    assert store.get_transactions(category="dining")[0].merchant == "A"
    assert store.get_transactions(account="cc")[0].merchant == "B"


def test_accounts_save_replace_and_get(tmp_path):
    store = SQLiteStructuredStore(tmp_path / "j.db")
    store.save_account(
        Account(id="chk", name="Checking", type="checking", balance=Decimal("1987.50"))
    )

    [account] = store.get_accounts()
    assert account.balance == Decimal("1987.50")

    store.save_account(
        Account(id="chk", name="Checking", type="checking", balance=Decimal("2000.00"))
    )
    accounts = store.get_accounts()
    assert len(accounts) == 1  # replaced, not duplicated
    assert accounts[0].balance == Decimal("2000.00")
