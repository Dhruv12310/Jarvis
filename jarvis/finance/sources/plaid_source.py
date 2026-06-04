"""Plaid transaction source - the ONLY module that imports plaid (boundary-guarded).

This is the one OUTBOUND finance path (the user's opt-in automation): transactions flow through
Plaid's aggregator. It implements the same `TransactionSource.load()` contract as the local CSV/OFX
sources, so the engine is identical regardless of source. Credentials come from `.env`.

IMPORTANT sign normalization: Plaid reports `amount` as POSITIVE when money leaves the account (the
opposite of OFX). Our model uses negative = outflow, so each Plaid amount is negated. The pure
`_normalize` function (no network) is unit-tested; `load()` does the API calls.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import plaid
from plaid.api import plaid_api
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest

from jarvis.config import config
from jarvis.finance.money import to_cents
from jarvis.finance.sources.base import TransactionSource
from jarvis.finance.transaction import Account, Transaction, make_id

_ENVIRONMENTS = {"sandbox": plaid.Environment.Sandbox, "production": plaid.Environment.Production}
# Account types whose Plaid balance is owed money (a debt). Plaid reports these as a POSITIVE
# `current`; net worth treats debt as negative, so we flip the sign for these (matching OFX).
_LIABILITY_TYPES = {"credit", "loan"}


class PlaidSource(TransactionSource):
    def __init__(
        self,
        *,
        client_id: str | None = None,
        secret: str | None = None,
        access_token: str | None = None,
        environment: str | None = None,
    ) -> None:
        self._client_id = client_id or config.plaid_client_id
        self._secret = secret or config.plaid_secret
        self._access_token = access_token or config.plaid_access_token
        self._environment = environment or config.plaid_environment

    def load(self) -> tuple[list[Transaction], list[Account]]:
        client = self._build_client()
        plaid_transactions = self._sync_transactions(client)
        plaid_accounts = client.accounts_get(
            AccountsGetRequest(access_token=self._access_token)
        ).accounts
        return _normalize(plaid_transactions, plaid_accounts)

    def _build_client(self):
        configuration = plaid.Configuration(
            host=_ENVIRONMENTS[self._environment],
            api_key={"clientId": self._client_id, "secret": self._secret},
        )
        return plaid_api.PlaidApi(plaid.ApiClient(configuration))

    def _sync_transactions(self, client) -> list:
        added, cursor = [], None
        while True:
            kwargs = {"access_token": self._access_token}
            if cursor:
                kwargs["cursor"] = cursor
            response = client.transactions_sync(TransactionsSyncRequest(**kwargs))
            added.extend(response.added)
            cursor = response.next_cursor
            if not response.has_more:
                break
        return added


def _normalize(plaid_transactions, plaid_accounts) -> tuple[list[Transaction], list[Account]]:
    transactions = []
    for t in plaid_transactions:
        # Plaid: +ve = outflow -> our convention: -ve = outflow. to_cents pins the precision since
        # the SDK yields a float (the one place a float touches money).
        amount = to_cents(-Decimal(str(t.amount)))
        merchant = (getattr(t, "merchant_name", None) or t.name or "").strip()
        txn_date = t.date if isinstance(t.date, date) else date.fromisoformat(str(t.date))
        account = str(t.account_id)
        transactions.append(
            Transaction(
                id=make_id(account, txn_date, amount, merchant),
                date=txn_date,
                amount=amount,
                merchant=merchant,
                category="uncategorized",
                account=account,
            )
        )
    accounts = []
    for a in plaid_accounts:
        account_type = str(a.type)
        current = a.balances.current
        balance = to_cents(Decimal(str(current))) if current is not None else Decimal("0.00")
        if account_type in _LIABILITY_TYPES:
            balance = -balance  # Plaid reports debt as positive; net worth needs it negative
        accounts.append(
            Account(id=str(a.account_id), name=a.name, type=account_type, balance=balance)
        )
    return transactions, accounts
