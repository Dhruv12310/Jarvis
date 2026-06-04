"""Categorization: deterministic rules first, then an LLM fallback for unknown merchants.

Precedence: user override > deterministic rule > LLM classification > "uncategorized". The LLM only
ever sees the merchant STRING and the fixed category list (a language task, like routing) - never an
amount or a computation. Corrections are stored as overrides and stick for future imports.
"""

from __future__ import annotations

import json
from dataclasses import replace

from jarvis.finance.transaction import Transaction

CATEGORIES = (
    "dining",
    "groceries",
    "transport",
    "shopping",
    "utilities",
    "entertainment",
    "health",
    "income",
    "transfer",
    "fees",
    "other",
)

# Deterministic merchant->category rules: a needle (matched case-insensitively as a substring of the
# merchant) maps to a category. Cheap, free, and the first line of categorization.
_RULES = {
    "STARBUCKS": "dining",
    "CHIPOTLE": "dining",
    "MCDONALD": "dining",
    "DOORDASH": "dining",
    "UBER EATS": "dining",
    "UBER": "transport",
    "LYFT": "transport",
    "SHELL": "transport",
    "CHEVRON": "transport",
    "AMAZON": "shopping",
    "TARGET": "shopping",
    "WALMART": "groceries",
    "WHOLE FOODS": "groceries",
    "TRADER JOE": "groceries",
    "SAFEWAY": "groceries",
    "NETFLIX": "entertainment",
    "SPOTIFY": "entertainment",
    "HULU": "entertainment",
    "COMCAST": "utilities",
    "PG&E": "utilities",
    "AT&T": "utilities",
    "PAYROLL": "income",
    "CVS": "health",
    "WALGREENS": "health",
}


class Categorizer:
    def __init__(self, *, overrides: dict[str, str] | None = None, llm=None) -> None:
        self._overrides = overrides or {}
        self._llm = llm  # optional; when absent, unknown merchants stay "uncategorized"

    def categorize(self, merchant: str) -> str:
        merchant = merchant.strip()
        if merchant in self._overrides:  # a stored user correction
            return self._overrides[merchant]
        upper = merchant.upper()
        for needle, category in _RULES.items():
            if needle in upper:
                return category
        if self._llm is not None:
            return self._classify_with_llm(merchant)
        return "uncategorized"

    def _classify_with_llm(self, merchant: str) -> str:
        # The model classifies the merchant STRING only - no amount is ever in this prompt.
        schema = {
            "type": "object",
            "properties": {"category": {"type": "string", "enum": list(CATEGORIES)}},
            "required": ["category"],
        }
        prompt = (
            "Classify this merchant name into exactly one spending category.\n"
            f"Merchant: {merchant}\n"
            f"Categories: {', '.join(CATEGORIES)}"
        )
        try:
            raw = self._llm.generate(prompt, format=schema, think=False)
            category = json.loads(raw).get("category", "")
            return category if category in CATEGORIES else "other"
        except Exception:
            return "uncategorized"  # categorization never breaks an import


def categorize_transactions(
    transactions: list[Transaction], categorizer: Categorizer
) -> list[Transaction]:
    """Return the transactions with categories assigned by the categorizer."""
    return [replace(t, category=categorizer.categorize(t.merchant)) for t in transactions]
