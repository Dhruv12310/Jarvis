"""Money formatting + cents quantization, and make_id stability across Decimal scale."""

from datetime import date
from decimal import Decimal

from jarvis.finance.money import format_money, to_cents
from jarvis.finance.transaction import make_id


def test_to_cents_rounds_to_two_places():
    assert to_cents(Decimal("12.5")) == Decimal("12.50")
    assert to_cents(Decimal("12.567")) == Decimal("12.57")


def test_format_money_two_places_grouped_no_scientific_notation():
    assert format_money(Decimal("1E+3")) == "$1,000.00"  # never "$1E+3"
    assert format_money(Decimal("-1000.5")) == "$-1,000.50"
    assert format_money(Decimal("57.5")) == "$57.50"


def test_make_id_is_stable_across_decimal_scale():
    # The same real transaction expressed as -12.5 or -12.50 must hash to the same id (no dup).
    a = make_id("chk", date(2026, 1, 5), Decimal("-12.5"), "STARBUCKS")
    b = make_id("chk", date(2026, 1, 5), Decimal("-12.50"), "STARBUCKS")
    assert a == b
