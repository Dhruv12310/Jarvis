"""CSV import (stdlib csv) - fully local. Expects a bank export with date/amount/description cols.

Amounts are signed Decimals (negative = outflow). CSV exports carry no running balance, so this
source returns no accounts. A handful of common date layouts are accepted.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from jarvis.finance.sources.base import TransactionSource
from jarvis.finance.transaction import Account, Transaction, make_id

_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d")


class CsvSource(TransactionSource):
    def __init__(self, path: Path | str, account: str = "csv") -> None:
        self._path = Path(path)
        self._account = account

    def load(self) -> tuple[list[Transaction], list[Account]]:
        transactions: list[Transaction] = []
        with open(self._path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
                txn_date = _parse_date(row["date"])
                amount = Decimal(row["amount"].replace(",", "").replace("$", ""))
                merchant = row.get("description") or row.get("merchant") or ""
                account = row.get("account") or self._account
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
        return transactions, []  # CSV has no balance -> no accounts


def _parse_date(value: str) -> date:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognized date: {value!r}")
