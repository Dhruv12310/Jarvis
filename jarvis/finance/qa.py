"""Finance Q&A: the LLM parses + phrases; the deterministic engine computes. The model never sums.

Flow: parse the natural-language question into a structured `FinanceQuery` (a language task, like
the router) -> the engine computes the EXACT figure from the stored transactions -> the LLM phrases
that figure (it is given the number; it does not, and must not, recompute it).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from jarvis.finance import engine
from jarvis.finance.categorize import CATEGORIES
from jarvis.finance.money import format_money

_METRICS = ("spending", "balance")
_PERIODS = ("this_month", "last_month", "all")


@dataclass(frozen=True)
class FinanceQuery:
    metric: str  # spending | balance
    category: str | None  # a category, or None for all spending
    period: str  # this_month | last_month | all


def parse_question(question: str, llm) -> FinanceQuery:
    """LLM parses the question into a validated FinanceQuery. Never computes a number."""
    schema = {
        "type": "object",
        "properties": {
            "metric": {"type": "string", "enum": list(_METRICS)},
            "category": {"type": ["string", "null"]},
            "period": {"type": "string", "enum": list(_PERIODS)},
        },
        "required": ["metric"],
    }
    prompt = (
        "Parse this finance question into fields (do not compute anything).\n"
        "metric: 'spending' or 'balance'.\n"
        f"category: one of {', '.join(CATEGORIES)}, or null for all spending.\n"
        "period: this_month, last_month, or all.\n"
        f"Question: {question}"
    )
    try:
        data = json.loads(llm.generate(prompt, format=schema, think=False))
    except Exception:
        data = {}
    metric = data.get("metric") if data.get("metric") in _METRICS else "spending"
    category = data.get("category") if data.get("category") in CATEGORIES else None
    period = data.get("period") if data.get("period") in _PERIODS else "this_month"
    return FinanceQuery(metric=metric, category=category, period=period)


def compute(query: FinanceQuery, transactions, accounts, today: date) -> tuple[Decimal, str]:
    """Deterministically compute the figure + a label for the query. The engine does the math."""
    if query.metric == "balance":
        return engine.net_worth(accounts), "net worth"
    start, end = _period_range(query.period, today)
    if query.category:
        value = engine.spending_by_category(transactions, start, end).get(
            query.category, Decimal(0)
        )
        label = f"spending on {query.category}"
    else:
        value = engine.total_spending(transactions, start, end)
        label = "total spending"
    return value, label + _period_suffix(query.period)


def phrase_prompt(question: str, label: str, value: Decimal) -> str:
    """The prompt the LLM phrases. It is given the EXACT figure and told not to change it."""
    return (
        "Answer the finance question in one short sentence using ONLY the figure below. "
        "Do not compute, change, or add any number.\n"
        f"Question: {question}\n"
        f"{label}: {format_money(value)}"
    )


def _period_range(period: str, today: date) -> tuple[date | None, date | None]:
    if period == "all":
        return None, None
    if period == "last_month":
        last_day_prev = today.replace(day=1) - timedelta(days=1)
        return last_day_prev.replace(day=1), last_day_prev
    return today.replace(day=1), today  # this_month


def _period_suffix(period: str) -> str:
    return {"this_month": " this month", "last_month": " last month", "all": ""}[period]
