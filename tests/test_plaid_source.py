"""Plaid source normalization (no network): the pure _normalize maps Plaid's model to our Decimal
model and FLIPS the sign (Plaid reports outflows as positive; we use negative = outflow).

A live `@integration` test (skipped unless a Plaid access token is configured, like OAuth) would
exercise the real /transactions/sync; it is not run by default.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from jarvis.config import config
from jarvis.finance.sources.plaid_source import _normalize


def _ptxn(amount, name, *, merchant_name=None, account_id="acc1", day=date(2026, 1, 5)):
    return SimpleNamespace(
        amount=amount, name=name, merchant_name=merchant_name, account_id=account_id, date=day
    )


def _paccount(account_id, name, type_, current):
    return SimpleNamespace(
        account_id=account_id, name=name, type=type_, balances=SimpleNamespace(current=current)
    )


def test_normalize_flips_the_sign_to_our_convention():
    # Plaid: amount 12.50 means money LEFT the account (a spend). Ours: negative = outflow.
    transactions, _ = _normalize([_ptxn(12.50, "STARBUCKS")], [])

    assert transactions[0].amount == Decimal("-12.50")
    assert transactions[0].merchant == "STARBUCKS"
    assert transactions[0].date == date(2026, 1, 5)


def test_normalize_inflow_becomes_positive():
    # Plaid reports inflows (e.g. payroll) as negative; ours becomes positive.
    transactions, _ = _normalize([_ptxn(-2000.00, "PAYROLL")], [])

    assert transactions[0].amount == Decimal("2000.00")


def test_normalize_prefers_merchant_name_over_raw_name():
    transactions, _ = _normalize([_ptxn(9.99, "SQ *COFFEE", merchant_name="Blue Bottle")], [])

    assert transactions[0].merchant == "Blue Bottle"


def test_normalize_accounts_to_decimal_balance():
    _, accounts = _normalize([], [_paccount("acc1", "Checking", "depository", 1987.50)])

    assert accounts[0].balance == Decimal("1987.50")
    assert accounts[0].type == "depository"


def test_normalize_flips_liability_balance_sign_for_net_worth():
    # Plaid reports a card's `current` (amount owed) as POSITIVE; net worth needs it negative.
    _, accounts = _normalize([], [_paccount("cc", "Card", "credit", 200.25)])

    assert accounts[0].balance == Decimal("-200.25")


@pytest.mark.integration
def test_plaid_sync_live():
    if not config.plaid_access_token:
        pytest.skip("Plaid not configured (set JARVIS_PLAID_* in .env to run)")
    from jarvis.finance.sources.plaid_source import PlaidSource

    transactions, accounts = PlaidSource().load()
    assert isinstance(transactions, list) and isinstance(accounts, list)
