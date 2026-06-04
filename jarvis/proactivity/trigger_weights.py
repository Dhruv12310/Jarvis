"""Per-kind reflection TRIGGER FUEL weights (deterministic) + the attention denylist.

This answers ONE question: does this signal warrant re-reflecting? It is NOT a reward label - the
(5c) feedback reward is a different number in a different module; never confuse the two. The weights
encode GENUINE SIGNIFICANCE (user-declared milestones, explicit corrections), never attention/dwell.
Attention-derived kinds are DENYLISTED to 0.0 so a passive view can never drive the learning loop -
the Core §8 guard, made code instead of prose.
"""

from __future__ import annotations

# Passive / attention-derived signal kinds. These NEVER contribute trigger fuel (Core §8): a view or
# a dwell must not pull the system toward reflecting on what merely grabbed attention.
DENYLIST = frozenset({"suggestion_shown", "item_dwell"})

# Fuel weights by signal kind. Higher = a stronger sign that something about the user genuinely
# changed and is worth re-reflecting on. Explicit user actions rank highest; inspectors lowest.
_FUEL = {
    "goal_done": 1.0,  # a user-declared milestone reached
    "remember": 0.9,  # the user explicitly said "remember this"
    "goal_add": 0.8,  # a new declared intention
    "recategorize": 0.6,  # an explicit correction reveals what the user cares about
    "budget_set": 0.6,  # an explicit financial intention
    "ask": 0.4,  # a question (a weak interest signal)
    "recall": 0.4,
    "finance_query": 0.4,
    "categorize": 0.3,
    "briefing": 0.3,
    "agenda": 0.2,
    "accounts": 0.2,
    "goal_list": 0.1,  # inspectors: just looking, barely significant
    "memory_list": 0.1,
    "budget_status": 0.1,
}
_DEFAULT_FUEL = 0.2  # an unknown kind counts a little, but never like a declared action


def trigger_fuel(kind: str) -> float:
    """Deterministic fuel for a signal kind. Attention-derived kinds are 0.0 (Core §8)."""
    if kind in DENYLIST:
        return 0.0
    return _FUEL.get(kind, _DEFAULT_FUEL)
