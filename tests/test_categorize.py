"""Categorization: deterministic rules, override precedence, the LLM fallback (merchant string only,
no amount), and corrections that persist + re-categorize stored transactions.
"""

import json
from datetime import date
from decimal import Decimal

from jarvis.finance.categorize import Categorizer, categorize_transactions
from jarvis.finance.transaction import Transaction, make_id
from jarvis.stores.sqlite_store import SQLiteStructuredStore


class _FakeLLM:
    def __init__(self, category="dining"):
        self._category = category
        self.prompts: list[str] = []

    def generate(self, prompt, *, format=None, think=None):
        self.prompts.append(prompt)
        return json.dumps({"category": self._category})


def _txn(merchant, category="uncategorized", *, day=date(2026, 1, 5), account="chk"):
    amt = Decimal("-9.99")
    return Transaction(make_id(account, day, amt, merchant), day, amt, merchant, category, account)


def test_rule_matches_a_known_merchant():
    assert Categorizer().categorize("STARBUCKS STORE 123") == "dining"


def test_override_beats_a_rule():
    # SHELL would be "transport" by rule; a user override wins.
    categorizer = Categorizer(overrides={"SHELL": "groceries"})

    assert categorizer.categorize("SHELL") == "groceries"


def test_unknown_merchant_stays_uncategorized_without_an_llm():
    assert Categorizer().categorize("OBSCURE LOCAL VENUE") == "uncategorized"


def test_unknown_merchant_uses_the_llm_on_the_string_only():
    llm = _FakeLLM("entertainment")

    category = Categorizer(llm=llm).categorize("OBSCURE LOCAL VENUE")

    assert category == "entertainment"
    [prompt] = llm.prompts
    assert "OBSCURE LOCAL VENUE" in prompt  # the model saw the merchant string...
    assert "$" not in prompt
    assert not any(ch.isdigit() for ch in prompt)  # ...and never an amount/figure of any kind


def test_llm_returning_an_invalid_category_falls_back_to_other():
    class _BadLLM:
        def generate(self, prompt, **kwargs):
            return json.dumps({"category": "not-a-real-category"})

    assert Categorizer(llm=_BadLLM()).categorize("XYZ") == "other"


def test_categorize_transactions_assigns_categories():
    txns = [_txn("STARBUCKS"), _txn("UBER")]

    out = categorize_transactions(txns, Categorizer())

    assert [t.category for t in out] == ["dining", "transport"]


def test_correction_persists_and_recategorizes(tmp_path):
    store = SQLiteStructuredStore(tmp_path / "j.db")
    store.save_transactions(
        [
            _txn("SHELL", "transport", day=date(2026, 1, 5)),
            _txn("SHELL", "transport", day=date(2026, 1, 20)),  # distinct id
            _txn("AMAZON", "shopping"),
        ]
    )

    store.save_category_override("SHELL", "groceries")
    updated = store.recategorize_merchant("SHELL", "groceries")

    assert updated == 2  # both SHELL rows, not AMAZON
    assert store.get_category_overrides() == {"SHELL": "groceries"}
    shell = [t for t in store.get_transactions() if t.merchant == "SHELL"]
    assert all(t.category == "groceries" for t in shell)
    # The stored override now drives a fresh categorizer (sticks for future imports).
    assert Categorizer(overrides=store.get_category_overrides()).categorize("SHELL") == "groceries"
