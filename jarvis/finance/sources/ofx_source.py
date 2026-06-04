"""OFX/QFX import via ofxtools - the ONLY module that imports ofxtools (boundary-guarded, local).

ofxtools already yields Decimal amounts and parsed dates; we normalize each STMTTRN into a
Transaction (category filled later) and each statement's ledger balance into an Account.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from ofxtools.Parser import OFXTree

from jarvis.finance.sources.base import TransactionSource
from jarvis.finance.transaction import Account, Transaction, make_id


class OfxSource(TransactionSource):
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    def load(self) -> tuple[list[Transaction], list[Account]]:
        tree = OFXTree()
        with open(self._path, "rb") as handle:
            tree.parse(handle)
        ofx = tree.convert()
        transactions: list[Transaction] = []
        accounts: list[Account] = []
        for statement in ofx.statements:
            account_id = str(statement.account.acctid)
            balance = statement.ledgerbal.balamt if statement.ledgerbal is not None else Decimal(0)
            accounts.append(
                Account(
                    id=account_id,
                    name=account_id,
                    type=str(statement.account.accttype).lower(),
                    balance=balance,
                )
            )
            for stmttrn in statement.transactions:
                transactions.append(_to_transaction(account_id, stmttrn))
        return transactions, accounts


def _to_transaction(account: str, stmttrn) -> Transaction:
    txn_date = stmttrn.dtposted.date()
    amount = stmttrn.trnamt  # ofxtools returns a Decimal
    merchant = (stmttrn.name or "").strip()
    return Transaction(
        id=make_id(account, txn_date, amount, merchant),
        date=txn_date,
        amount=amount,
        merchant=merchant,
        category="uncategorized",
        account=account,
    )
