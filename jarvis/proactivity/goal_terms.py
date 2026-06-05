"""Deterministic extraction of PUBLIC query terms from a free-text goal (no LLM, no I/O).

A goal description is private text, but the *terms* we derive from it (a ticker, a topic keyword)
become outbound collector queries, so this module is the trust-boundary chokepoint: it must emit
only generic, public-shaped terms. It is a pure function of a string - no clock, no store, no
network, no model - so it is fully unit-testable and cannot leak a secret.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Mirror the markets connector's ticker shape, but we OWN this copy (proactivity must not import a
# connector - the boundary tests forbid it). A ticker is 1-5 uppercase letters.
_TICKER = re.compile(r"\b[A-Z]{1,5}\b")
# Uppercase tokens that look like tickers but are not (kept in spirit with markets._NOT_TICKERS).
_NOT_TICKERS = {
    "AI",
    "I",
    "A",
    "US",
    "CEO",
    "IPO",
    "ETF",
    "LLM",
    "HN",
    "YC",
    "Q1",
    "Q2",
    "Q3",
    "Q4",
    "API",
    "ML",
    "UI",
    "OS",
    "PR",
    "TODO",
    "LLC",
    "SAAS",
    "MVP",
    "B2B",
    "B2C",
    "SDK",
    "APP",
}
# Words that carry no retrieval signal. Goals are imperative ("learn X", "ship Y"), so verbs like
# learn/build/ship are noise as search terms; we want the OBJECT nouns.
_STOPWORDS = {
    "the",
    "a",
    "an",
    "to",
    "of",
    "for",
    "and",
    "or",
    "in",
    "on",
    "at",
    "by",
    "with",
    "my",
    "me",
    "i",
    "we",
    "our",
    "this",
    "that",
    "these",
    "those",
    "is",
    "are",
    "be",
    "learn",
    "build",
    "ship",
    "make",
    "do",
    "get",
    "start",
    "finish",
    "complete",
    "improve",
    "study",
    "read",
    "write",
    "plan",
    "track",
    "save",
    "buy",
    "sell",
    "invest",
    "grow",
    "goal",
    "goals",
    "project",
    "want",
    "need",
    "should",
    "will",
    "more",
    "less",
    "into",
    "up",
    "down",
    "out",
    "about",
    "from",
    "as",
    "it",
    "so",
    "then",
    "next",
    "new",
    "create",
}
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9.+\-]*")


@dataclass(frozen=True)
class GoalTerms:
    """The public query terms a goal resolves to. `symbols` -> markets; `topics` -> news/hn."""

    symbols: list[str]  # candidate tickers (upper-cased)
    topics: list[str]  # keyword/phrase topics for news + HN


def _topics(text: str, *, max_topics: int) -> list[str]:
    """Content words, stopword-filtered, de-duplicated, original order preserved.

    Also emits adjacent-pair bigrams ("personal finance") before single words, because a two-word
    phrase is a sharper news query than either word alone."""
    words = _WORD.findall(text)
    keep = [w for w in words if w.lower() not in _STOPWORDS and len(w) > 2]
    seen: set[str] = set()
    out: list[str] = []
    # Bigrams of consecutive kept words first (more specific), then unigrams.
    for a, b in zip(keep, keep[1:], strict=False):
        phrase = f"{a} {b}"
        if phrase.lower() not in seen:
            seen.add(phrase.lower())
            out.append(phrase)
    for w in keep:
        if w.lower() not in seen:
            seen.add(w.lower())
            out.append(w)
    return out[:max_topics]


def extract_terms(goal_description: str, *, max_topics: int = 3) -> GoalTerms:
    """Deterministically split a goal into candidate tickers and topic phrases (no LLM).

    Only literal all-caps tokens become symbols, so 'amazon' stays a news topic while 'AMZN' routes
    to markets - we never invent a finance query from a non-finance goal."""
    text = goal_description or ""
    symbols = [t for t in _TICKER.findall(text) if t not in _NOT_TICKERS]
    symbols = list(dict.fromkeys(symbols))  # de-dup, keep order
    topics = _topics(text, max_topics=max_topics)
    return GoalTerms(symbols=symbols, topics=topics)
