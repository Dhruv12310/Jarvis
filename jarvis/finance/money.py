"""Money helpers. One place to quantize to cents and to format for display.

Quantizing to cents keeps the deterministic transaction id stable across sources (so -12.5 and
-12.50 are the same row) and keeps displayed figures clean (no scientific notation, always 2dp).
"""

from __future__ import annotations

from decimal import Decimal

_CENTS = Decimal("0.01")


def to_cents(value: Decimal) -> Decimal:
    """Round a money value to cents (the canonical stored/compared form)."""
    return value.quantize(_CENTS)


def format_money(value: Decimal) -> str:
    """Format a money value for display: $-1,234.50 (2dp, grouped, no scientific notation)."""
    return f"${to_cents(value):,.2f}"
