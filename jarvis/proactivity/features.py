"""Ranking features (Core §7.2). Each is a calibrated [0,1], monotone, PURE function - no LLM, no
HTTP, no config, and NEVER an attention/dwell/engagement input. The ranker (rank.py) weights and
sums them; these only describe usefulness. interest_match leans on the 5a guarantee that a
pure-frequency interest has weight 0.0, so a compulsion contributes nothing to a candidate's score.
"""

from __future__ import annotations

from datetime import UTC, datetime
from math import exp

_PRIORITY = {"high": 1.0, "medium": 0.6, "low": 0.3}


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def _topic_matches(topics, text: str) -> bool:
    t = text.lower()
    return any(topic.lower() in t or t in topic.lower() for topic in topics if topic)


def goal_relevance(candidate, goals) -> float:
    """Does this candidate serve an active goal? Graded by the goal's priority; 0 if none."""
    best = 0.0
    for g in goals:
        if getattr(g, "status", "active") != "active":
            continue
        linked = candidate.entity_key == f"goal:{g.id}" or _topic_matches(
            candidate.topics, g.description
        )
        if linked:
            best = max(best, _PRIORITY.get(g.priority, 0.6))
    return best


def urgency(candidate, *, horizon_hours: float) -> float:
    """Monotone-decreasing in time-to-deadline/event; budgets use how far over the limit."""
    f = candidate.features
    if "deadline_hours" in f:
        hours = f["deadline_hours"]
    elif "start_hours" in f:
        hours = f["start_hours"]
    elif "days_until" in f:
        hours = f["days_until"] * 24.0
    elif "over_ratio" in f:
        return min(1.0, max(0.0, f["over_ratio"] - 1.0))  # 1.25x over -> 0.25
    else:
        return 0.0
    if hours <= 0:
        return 1.0  # due now or overdue
    return max(0.0, 1.0 - hours / horizon_hours)


def interest_match(candidate, interests) -> float:
    """Max goal-linked Interest.weight over topic matches. §8: weight is 0.0 for pure frequency."""
    best = 0.0
    for it in interests:
        if _topic_matches(candidate.topics, it.topic):
            best = max(best, it.weight)
    return min(1.0, max(0.0, best))


def in_quiet_hours(now: datetime, start: int, end: int) -> bool:
    h = _aware(now).hour
    if start == end:
        return False
    if start < end:
        return start <= h < end
    return h >= start or h < end  # window wraps midnight (e.g. 22 -> 07)


def timing_fit(now: datetime, rhythms, *, quiet_hours) -> float:
    """1.0 at an ordinary moment, 0.0 inside quiet hours. (Rhythm-aware refinement is future.)"""
    start, end = quiet_hours
    return 0.0 if in_quiet_hours(now, start, end) else 1.0


def novelty(candidate, recent, *, now: datetime, lam: float) -> float:
    """Incremental value: 1.0 if never surfaced; ~0 just after; rising toward 1 as time passes."""
    last = None
    for s in recent:
        if s.entity_key == candidate.entity_key:
            ts = _aware(s.created_at)
            if last is None or ts > last:
                last = ts
    if last is None:
        return 1.0
    hours = max(0.0, (_aware(now) - last).total_seconds() / 3600.0)
    return 1.0 - exp(-lam * hours)


def recent_interruption_penalty(recent, *, now: datetime, window_hours: float, cap: int) -> float:
    """The -fatigue term: how full the recent window already is (saturates at the cap)."""
    if not cap:
        return 0.0
    n = sum(
        1
        for s in recent
        if (_aware(now) - _aware(s.created_at)).total_seconds() / 3600.0 <= window_hours
    )
    return min(1.0, n / cap)
