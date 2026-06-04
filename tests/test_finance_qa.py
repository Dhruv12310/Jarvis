"""Finance Q&A: the LLM parses + phrases, the engine computes. The figure in the answer is the
engine's number, never a model-invented one - and the signal log carries no amount.
"""

import json
from datetime import date
from decimal import Decimal

from jarvis.finance import engine, qa
from jarvis.finance.transaction import Account, Transaction, make_id
from jarvis.orchestrator import Orchestrator
from jarvis.service import JarvisService
from jarvis.signals.log import SignalLog
from jarvis.stores.sqlite_store import SQLiteStructuredStore


class _ParseLLM:
    """Fake structured-parse LLM: returns a fixed FinanceQuery dict, records the prompt."""

    def __init__(self, query):
        self._query = query

    def generate(self, prompt, *, format=None, think=None):
        self.prompt = prompt
        return json.dumps(self._query)


class _EchoLLM:
    def generate(self, prompt, **kwargs):
        return prompt  # echo, so the phrased "answer" contains the engine figure verbatim


def _txn(day, amount, merchant, category):
    amt = Decimal(amount)
    return Transaction(make_id("chk", day, amt, merchant), day, amt, merchant, category, "chk")


LEDGER = [
    _txn(date(2026, 1, 5), "-12.50", "STARBUCKS", "dining"),
    _txn(date(2026, 1, 12), "-30.00", "CHIPOTLE", "dining"),
    _txn(date(2026, 1, 20), "-15.00", "UBER", "transport"),
]


def test_parse_question_returns_a_validated_query():
    llm = _ParseLLM({"metric": "spending", "category": "dining", "period": "all"})

    query = qa.parse_question("how much on dining", llm)

    assert query == qa.FinanceQuery(metric="spending", category="dining", period="all")


def test_parse_falls_back_on_garbage_output():
    class _Bad:
        def generate(self, prompt, **kwargs):
            return "not json"

    query = qa.parse_question("x", _Bad())

    assert query.metric == "spending" and query.period == "this_month"


def test_compute_spending_by_category_uses_the_engine():
    value, label = qa.compute(
        qa.FinanceQuery("spending", "dining", "all"), LEDGER, [], date(2026, 2, 1)
    )

    assert value == Decimal("42.50")  # 12.50 + 30.00, computed by the engine
    assert "dining" in label


def test_compute_total_and_balance():
    total, _ = qa.compute(qa.FinanceQuery("spending", None, "all"), LEDGER, [], date(2026, 2, 1))
    assert total == Decimal("57.50")

    accounts = [
        Account("chk", "Checking", "checking", Decimal("100.00")),
        Account("cc", "Card", "credit", Decimal("-25.00")),
    ]
    net, label = qa.compute(qa.FinanceQuery("balance", None, "all"), [], accounts, date(2026, 2, 1))
    assert net == Decimal("75.00") and "net worth" in label


def test_compute_this_month_window():
    # today = 2026-02-01 -> "this month" excludes January's transactions.
    value, _ = qa.compute(
        qa.FinanceQuery("spending", None, "this_month"), LEDGER, [], date(2026, 2, 1)
    )
    assert value == Decimal("0")


def test_phrase_prompt_carries_the_exact_figure_and_forbids_recompute():
    prompt = qa.phrase_prompt("how much on dining", "spending on dining", Decimal("42.50"))

    assert "$42.50" in prompt
    assert "only the figure" in prompt.lower()


def test_finance_answer_figure_is_the_engines_number(tmp_path):
    store = SQLiteStructuredStore(tmp_path / "j.db")
    store.save_transactions(LEDGER)
    service = JarvisService(
        orchestrator=Orchestrator(_EchoLLM()),  # echoes the phrasing prompt
        knowledge=None,
        store=store,
        memory=None,
        signals=SignalLog(store, session_id="s"),
        source="cli",
        llm=_ParseLLM({"metric": "spending", "category": None, "period": "all"}),
    )

    answer = service.finance_answer("how much have I spent in total")

    # The answer carries the ENGINE's exact figure, not a model-invented one.
    assert f"${engine.total_spending(LEDGER)}" in answer  # $57.50
    [sig] = store.get_signals()
    assert sig.kind == "finance_query"
    assert sig.payload["metric"] == "spending"
    assert "57.50" not in str(sig.payload)  # no amount in the signal log
