"""The usefulness ranker + gate (Core §7.2, "the soul of the system").

Deterministic and explainable: the score is a weighted sum of calibrated [0,1] features, and the
per-feature contributions ARE the "why am I seeing this?" (no LLM verdict). Three §8 properties are
structural, not prose: abstention is the DEFAULT (an ABSOLUTE threshold, never min-max - min-max on
a tiny pool would normalize one candidate to 1.0 and destroy abstention); the frequency cap is a
config CONSTANT outside the scorer, so no score or feedback can ever raise volume; and the LLM
never ranks or selects. The most common correct output is an empty list.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from jarvis.config import config
from jarvis.proactivity import bandit
from jarvis.proactivity import features as F
from jarvis.proactivity.candidate import Candidate


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: Candidate
    score: float
    contributions: dict  # per-feature beta*f; sums to score -> the printable "why"


def usefulness(candidate, state) -> tuple[float, dict]:
    interests = getattr(state.user_model, "interests", []) if state.user_model else []
    rhythms = getattr(state.user_model, "rhythms", []) if state.user_model else []
    quiet = (config.quiet_hours_start, config.quiet_hours_end)
    # Learned multipliers (§7.5/5c) tune the hand-set base weights; default 1.0 = no learning yet.
    w = state.feedback_weights or {}
    contributions = {
        "goal": config.beta_goal * w.get("goal", 1.0) * F.goal_relevance(candidate, state.goals),
        "urgency": config.beta_urgency
        * w.get("urgency", 1.0)
        * F.urgency(candidate, horizon_hours=config.urgency_horizon_hours),
        "interest": config.beta_interest
        * w.get("interest", 1.0)
        * F.interest_match(candidate, interests),
        "timing": config.beta_timing
        * w.get("timing", 1.0)
        * F.timing_fit(state.now, rhythms, quiet_hours=quiet),
        "novelty": config.beta_novelty
        * w.get("novelty", 1.0)
        * F.novelty(candidate, state.recent_suggestions, now=state.now, lam=config.novelty_lambda),
        "fatigue": -config.beta_fatigue
        * F.recent_interruption_penalty(
            state.recent_suggestions,
            now=state.now,
            window_hours=config.suggestion_window_hours,
            cap=config.suggestions_per_window,
        ),
    }
    return sum(contributions.values()), contributions


def select(candidates, state) -> list[ScoredCandidate]:
    """Score -> abstain -> DND -> cooldown -> per-category cap -> global cap -> top-K."""
    # DND: when proactivity is off or it is quiet hours, the system stays silent. Period.
    if not config.proactivity_enabled or F.in_quiet_hours(
        state.now, config.quiet_hours_start, config.quiet_hours_end
    ):
        return []

    scored = []
    for c in candidates:
        score, contributions = usefulness(c, state)
        if score >= config.usefulness_threshold:  # absolute abstention threshold (set HIGH)
            scored.append(ScoredCandidate(c, score, contributions))

    # Per-entity cooldown: never re-surface something shown within the cooldown window.
    scored = [
        s
        for s in scored
        if not _in_cooldown(s.candidate.entity_key, state.recent_suggestions, state.now)
    ]
    # Per-category dismissal backoff (§7.3): a chronically-dismissed category is suppressed.
    cat_outcomes = state.category_outcomes
    scored = [
        s
        for s in scored
        if not bandit.cooldown_active(
            s.candidate.type,
            cat_outcomes,
            state.now,
            base_days=config.category_cooldown_base_days,
            cap_days=config.category_cooldown_cap_days,
        )
    ]
    # Explore/exploit RE-RANK (§7.3): order survivors by base_score * the bandit's per-category
    # multiplier. This only reorders what already cleared the bar - it never changes whether we
    # surface or the volume (the structural cap below still bounds it). §8: exploration picks the
    # slot, not the cap.
    scored.sort(
        key=lambda s: s.score * bandit.category_multiplier(s.candidate.type, cat_outcomes),
        reverse=True,
    )

    # Structural caps (outside the score): per-category, then a global per-window ceiling.
    surfaced = sum(
        1
        for r in state.recent_suggestions
        if _hours_since(state.now, r.created_at) <= config.suggestion_window_hours
    )
    room = max(0, config.suggestions_per_window - surfaced)
    out: list[ScoredCandidate] = []
    per_category: dict[str, int] = {}
    for s in scored:
        if len(out) >= room:
            break
        cat = s.candidate.type
        if per_category.get(cat, 0) >= config.per_category_cap:
            continue
        per_category[cat] = per_category.get(cat, 0) + 1
        out.append(s)
    return out


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def _hours_since(now: datetime, then: datetime) -> float:
    return (_aware(now) - _aware(then)).total_seconds() / 3600.0


def _in_cooldown(entity_key: str, recent, now: datetime) -> bool:
    return any(
        r.entity_key == entity_key
        and _hours_since(now, r.created_at) <= config.entity_cooldown_hours
        for r in recent
    )
