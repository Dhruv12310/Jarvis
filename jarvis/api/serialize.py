"""Deterministic dataclass -> JSON-able conversion for the API layer.

The facade returns frozen dataclasses (AskResult, Goal, Suggestion, Account, BudgetStatus, ...)
carrying datetime/date/Decimal leaves that the stdlib json encoder cannot serialize. This one pure
helper walks any of them into plain dict/list/str/number values: datetimes -> ISO 8601 strings,
Decimal -> string (exactness preserved; the client formats for display). No fastapi import here, so
it is unit-testable on its own.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def to_jsonable(obj: Any) -> Any:
    """Recursively convert dataclasses + datetime/date/Decimal into JSON-serializable values."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    if is_dataclass(obj) and not isinstance(obj, type):
        return {key: to_jsonable(value) for key, value in asdict(obj).items()}
    if isinstance(obj, dict):
        return {key: to_jsonable(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(value) for value in obj]
    return obj
