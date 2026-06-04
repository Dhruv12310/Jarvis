"""Candidates and the engine state they are generated from (Core Stage 6 - candidate generation).

A Candidate is a thing Jarvis COULD surface, produced deterministically by a generator from an
injected EngineState snapshot - no I/O lives here. Provenance is the deterministic "why am I seeing
this?": which generator fired and the source records it resolves to. The ranker (5b/slice 3) scores
candidates; the engine (slice 4) does all the I/O + phrasing. Generators stay pure and testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class Provenance:
    generator: str  # which generator fired ("goal_deadline", "market_move", ...)
    reason: str  # deterministic human "why" ("Goal #7 'ship 5b' is due in 2 day(s).")
    source_ids: list[str]  # ids that resolve to real records ("goal:7", "budget:dining", ...)


@dataclass(frozen=True)
class Fetched:
    """One collector item paired with the PUBLIC watchlist term it was fetched for (so a candidate
    can carry its provenance + topic without the generator ever touching HTTP)."""

    source: str  # connector name: markets | news | hn
    term: str  # the public watchlist term this item answers (never private text)
    item: object  # connectors.base.Item (kept loose so this module imports no connector)


@dataclass(frozen=True)
class Candidate:
    type: str  # candidate_type enum (§5.5): goal_nudge|budget_alert|followup_due|free_time|...
    entity_key: str  # dedup + cooldown key ("goal:7", "budget:dining", "symbol:NVDA")
    features: dict  # raw deterministic scalar inputs for the ranker (deadline_hours, days_until)
    provenance: Provenance
    payload: dict  # LOCAL data the phraser needs; never a signal/attention field, never logged raw
    topics: list[str] = field(default_factory=list)  # what it's "about", for interest_match (5b S3)


@dataclass(frozen=True)
class EngineState:
    """A frozen snapshot the engine gathers ONCE and hands to the pure generators/ranker. Grows in
    later slices (user model, recent suggestions)."""

    now: datetime
    goals: list = field(default_factory=list)  # active Goal[]
    budget_status: list = field(default_factory=list)  # BudgetStatus[]
    transactions: list = field(default_factory=list)  # Transaction[]
    events: list = field(default_factory=list)  # CalendarEvent[] (today/upcoming)
    connector_items: list = field(default_factory=list)  # Fetched[] (collector items + their term)
    user_model: object = None  # the 5a UserModel the ranker scores against
    recent_suggestions: list = field(default_factory=list)  # for novelty + cooldown + fatigue
    feedback_weights: dict = field(default_factory=dict)  # learned per-feature multipliers (§7.5)
    category_outcomes: list = field(
        default_factory=list
    )  # per-category feedback for the bandit (§7.3)


class CandidateGenerator(Protocol):
    """A pure (state) -> [Candidate] trigger. No facade, HTTP, LLM, or clock - state is injected."""

    def __call__(self, state: EngineState) -> list[Candidate]: ...
