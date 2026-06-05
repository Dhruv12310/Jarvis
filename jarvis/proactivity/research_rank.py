"""Deterministic relevance re-ranking of goal-feed items against a goal's public terms.

PURE: no LLM, no I/O, no module-level clock (``now`` is injected) - it lives under proactivity/ so
the LLM-free boundary test covers it. The goal feed fetches items by goal-derived terms, then this
orders them by how well each matches those terms (favoring recency and source), so the most relevant
papers and stories rise within the structural cap. Matching is substring containment of the PUBLIC
terms in the item title - the same terms extract_terms() already deemed safe to send outbound.

Two rules from the design review:
  - Zero-overlap arXiv PAPERS are dropped (the >=1-matched-term gate); other kinds were already
    fetched BY a goal term, so they are only reordered, never dropped (a topic like "saas" need not
    appear verbatim in a related headline).
  - Only fetched items are ranked; owned suggestions are handled by the caller and never reordered.
"""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime

from jarvis.config import config
from jarvis.proactivity.goal_terms import GoalTerms

_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")  # the YYYY-MM-DD inside a GoalFeedItem.detail


def rank(terms: GoalTerms, items: list, *, now: datetime) -> list:
    """Reorder fetched goal-feed items by deterministic relevance to ``terms`` (descending).

    Stable total order: score, then recency, then source name, then title. Drops only paper items
    with no matched term. With no terms there is nothing to score, so input order is preserved."""
    all_terms = [*terms.symbols, *terms.topics]
    if not all_terms:
        return items
    scored = []
    for item in items:
        matched = _matched(all_terms, item.title)
        if getattr(item, "kind", "") == "paper" and not matched:
            continue  # the >=1-matched-term gate: never surface an irrelevant paper
        recency = _recency(getattr(item, "detail", ""), now)
        score = (
            config.research_w_overlap * (len(matched) / len(all_terms))
            + config.research_w_recency * recency
            + config.research_w_source * config.research_source_weights.get(item.source, 0.5)
        )
        scored.append((score, recency, item.source, item.title, item))
    # Sort by score desc, recency desc, then source/title asc for a fully deterministic order.
    scored.sort(key=lambda t: (-t[0], -t[1], t[2], t[3]))
    return [t[4] for t in scored]


def _matched(all_terms: list[str], title: str) -> list[str]:
    title_lower = (title or "").lower()
    return [t for t in all_terms if t.lower() in title_lower]


def _recency(detail: str, now: datetime) -> float:
    """exp(-lambda * age_hours) from the date in ``detail``; neutral 0.5 when there is no date."""
    match = _DATE.search(detail or "")
    if not match:
        return 0.5
    try:
        published = datetime(int(match[1]), int(match[2]), int(match[3]), tzinfo=UTC)
    except ValueError:
        return 0.5
    age_hours = max(0.0, (now - published).total_seconds() / 3600.0)
    return math.exp(-config.research_recency_lambda * age_hours)
