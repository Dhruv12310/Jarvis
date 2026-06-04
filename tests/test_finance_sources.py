"""Transaction sources normalize a local file into Decimal Transactions (no network)."""

from datetime import date
from decimal import Decimal

import pytest

from jarvis.finance.sources import source_for
from jarvis.finance.sources.csv_source import CsvSource

_OFX = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<SIGNONMSGSRSV1><SONRS><STATUS><CODE>0<SEVERITY>INFO</STATUS><DTSERVER>20260201120000<LANGUAGE>ENG</SONRS></SIGNONMSGSRSV1>
<BANKMSGSRSV1><STMTTRNRS><TRNUID>0<STATUS><CODE>0<SEVERITY>INFO</STATUS>
<STMTRS><CURDEF>USD<BANKACCTFROM><BANKID>123<ACCTID>9999<ACCTTYPE>CHECKING</BANKACCTFROM>
<BANKTRANLIST><DTSTART>20260101<DTEND>20260131
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260105120000<TRNAMT>-12.50
<FITID>A1<NAME>STARBUCKS STORE 123<MEMO>coffee</STMTTRN>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260110<TRNAMT>2000.00
<FITID>A2<NAME>ACME PAYROLL</STMTTRN>
</BANKTRANLIST><LEDGERBAL><BALAMT>1987.50<DTASOF>20260131</LEDGERBAL></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""


def test_csv_source_normalizes_to_decimal(tmp_path):
    path = tmp_path / "tx.csv"
    path.write_text(
        "date,amount,description\n2026-01-05,-12.50,STARBUCKS\n2026-01-10,2000.00,PAYROLL\n",
        encoding="utf-8",
    )

    transactions, accounts = source_for(path).load()

    assert accounts == []  # CSV carries no balance
    assert [t.amount for t in transactions] == [Decimal("-12.50"), Decimal("2000.00")]
    assert transactions[0].merchant == "STARBUCKS"
    assert transactions[0].date == date(2026, 1, 5)


def test_csv_source_id_is_deterministic(tmp_path):
    path = tmp_path / "tx.csv"
    path.write_text("date,amount,description\n2026-01-05,-12.50,STARBUCKS\n", encoding="utf-8")

    first = CsvSource(path).load()[0][0].id
    second = CsvSource(path).load()[0][0].id

    assert first == second  # same row -> same id -> idempotent import


def test_ofx_source_normalizes_transactions_and_balance(tmp_path):
    path = tmp_path / "tx.ofx"
    path.write_bytes(_OFX)

    transactions, accounts = source_for(path).load()

    assert [t.amount for t in transactions] == [Decimal("-12.50"), Decimal("2000.00")]
    assert transactions[0].merchant == "STARBUCKS STORE 123"
    assert transactions[0].date == date(2026, 1, 5)
    assert accounts[0].balance == Decimal("1987.50")
    assert accounts[0].type == "checking"


def test_csv_inflow_stays_positive_and_is_not_spending(tmp_path):
    # CSV is the only raw-signed source: a positive deposit stays positive and is not spending.
    from jarvis.finance import engine

    path = tmp_path / "tx.csv"
    path.write_text("date,amount,description\n2026-01-10,2000.00,PAYROLL\n", encoding="utf-8")

    transactions, _ = source_for(path).load()

    assert transactions[0].amount == Decimal("2000.00")
    assert engine.total_spending(transactions) == Decimal("0")


def test_source_for_rejects_unknown_extension(tmp_path):
    with pytest.raises(ValueError):
        source_for(tmp_path / "statement.pdf")
