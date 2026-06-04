"""Per-category explore/exploit (Core §7.3) - deterministic, single-user, sparse-data.

Each suggestion CATEGORY is an arm with a Beta posterior over "was it useful?", seeded with a
PESSIMISTIC prior Beta(1, 3) so an untried category must earn its airtime (the cold-start trap: an
optimistic prior over-surfaces weak arms). A category's multiplier = posterior mean + a UCB-style
uncertainty bonus that shrinks with evidence - so chronically-dismissed categories are down-weighted
(exploit) while under-tried ones get a bounded lift (explore), with NO randomness.

CRITICAL (§8): this only RE-RANKS candidates that already cleared the absolute usefulness threshold,
and dismissal only ever ADDS a cooldown. Exploration changes WHICH slot fills - never whether we
surface, never the volume (the structural cap still bounds it). A dismissal can only suppress.
"""

from __future__ import annotations

from datetime import UTC, datetime
from math import sqrt

from jarvis.proactivity.feedback import reward

# Pessimistic prior: an untried category starts at a 25% "useful" estimate, not 50%.
_PRIOR_ALPHA, _PRIOR_BETA = 1.0, 3.0
_BONUS_C = 1.0  # exploration weight on the uncertainty bonus
_MULT_LO, _MULT_HI = 0.3, 1.3  # the multiplier band (re-ranking only; never inflates volume)


def _counts(category: str, category_outcomes) -> tuple[int, int]:
    positive = sum(1 for o in category_outcomes if o.category == category and reward(o.result) > 0)
    negative = sum(1 for o in category_outcomes if o.category == category and reward(o.result) < 0)
    return positive, negative


def value_estimate(category: str, category_outcomes) -> float:
    """Posterior mean P(useful) for a category, under the pessimistic prior."""
    positive, negative = _counts(category, category_outcomes)
    a, b = _PRIOR_ALPHA + positive, _PRIOR_BETA + negative
    return a / (a + b)


def category_multiplier(category: str, category_outcomes) -> float:
    """Exploit + explore as one deterministic factor: mean + an uncertainty bonus that decays with
    evidence. Clamped to a band; it only re-orders survivors, never lifts one over the bar."""
    positive, negative = _counts(category, category_outcomes)
    a, b = _PRIOR_ALPHA + positive, _PRIOR_BETA + negative
    mean = a / (a + b)
    bonus = _BONUS_C / sqrt(a + b)  # high when little is known (explore), -> 0 with evidence
    return max(_MULT_LO, min(_MULT_HI, mean + bonus))


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def cooldown_active(
    category: str, category_outcomes, now: datetime, *, base_days: float, cap_days: float
) -> bool:
    """Per-category exponential backoff: consecutive recent dismissals suppress the category for
    base_days * 2^(n-1) (capped). A single dismissal -> base_days; two -> 2x; three -> 4x; ..."""
    history = sorted(
        (o for o in category_outcomes if o.category == category),
        key=lambda o: o.ts,
        reverse=True,
    )
    consecutive = 0
    last_ts = None
    for o in history:
        if o.result == "dismissed":
            consecutive += 1
            if last_ts is None:
                last_ts = o.ts
        else:
            break
    if consecutive == 0:
        return False
    days = min(cap_days, base_days * (2 ** (consecutive - 1)))
    hours_since = (_aware(now) - _aware(last_ts)).total_seconds() / 3600.0
    return hours_since < days * 24
