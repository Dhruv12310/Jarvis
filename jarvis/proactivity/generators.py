"""Deterministic candidate generators (Core Stage 6 - candidate generation; high recall, cheap).

Each generator is a PURE function of an injected EngineState: no facade, no HTTP, no LLM, no clock.
The engine (slice 4) gathers the state and does all I/O; here we only turn owned data (goals,
budget, recurring charges, calendar) into Candidates, each tagged with deterministic provenance.
Slice 2 adds collector-driven generators; the registry + generate_all dedup the union by entity_key.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from jarvis.config import config
from jarvis.finance.engine import recurring_charges
from jarvis.proactivity.candidate import Candidate, EngineState, Provenance

_CADENCE_DAYS = {"weekly": 7, "biweekly": 14, "monthly": 30}


def _aware(dt: datetime) -> datetime:
    """Treat a naive datetime (e.g. from the store) as UTC so comparisons never raise."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def _days_or_hours(hours: float) -> str:
    return f"{round(hours)}h" if hours < 24 else f"{round(hours / 24)} day(s)"


def goal_deadline(state: EngineState) -> list[Candidate]:
    """An active goal whose deadline is within (or past) the urgency horizon -> a nudge."""
    horizon = timedelta(hours=config.urgency_horizon_hours)
    now = _aware(state.now)
    out = []
    for g in state.goals:
        if g.status != "active" or g.deadline is None:
            continue
        deadline = _aware(g.deadline)
        if deadline > now + horizon:
            continue
        hours = (deadline - now).total_seconds() / 3600.0
        when = "overdue" if hours < 0 else f"due in {_days_or_hours(hours)}"
        out.append(
            Candidate(
                type="goal_nudge",
                entity_key=f"goal:{g.id}",
                features={"deadline_hours": hours},
                provenance=Provenance(
                    generator="goal_deadline",
                    reason=f"Goal #{g.id} '{g.description}' is {when}.",
                    source_ids=[f"goal:{g.id}"],
                ),
                payload={
                    "goal_id": g.id,
                    "description": g.description,
                    "deadline": deadline.isoformat(),
                    "priority": g.priority,
                },
            )
        )
    return out


def stale_goal(state: EngineState) -> list[Candidate]:
    """An active, unfinished goal gone untouched (proxy: old created_at, no near deadline)."""
    horizon = timedelta(hours=config.urgency_horizon_hours)
    now = _aware(state.now)
    cutoff = now - timedelta(days=config.stale_goal_days)
    out = []
    for g in state.goals:
        if g.status != "active" or g.progress >= 1.0:
            continue
        if _aware(g.created_at) > cutoff:
            continue  # too fresh to be stale
        if g.deadline is not None and _aware(g.deadline) <= now + horizon:
            continue  # goal_deadline owns near-deadline goals (dedup at the source)
        age_days = (now - _aware(g.created_at)).days
        out.append(
            Candidate(
                type="goal_nudge",
                entity_key=f"goal:{g.id}",
                features={"age_days": float(age_days)},
                provenance=Provenance(
                    generator="stale_goal",
                    reason=f"Goal #{g.id} '{g.description}' untouched for {age_days} days.",
                    source_ids=[f"goal:{g.id}"],
                ),
                payload={"goal_id": g.id, "description": g.description, "progress": g.progress},
            )
        )
    return out


def budget_threshold(state: EngineState) -> list[Candidate]:
    """A budget that is over its limit, or within budget_near_fraction of it."""
    near_fraction = Decimal(str(config.budget_near_fraction))
    out = []
    for b in state.budget_status:
        near = b.remaining < b.limit * near_fraction
        if not (b.over or near):
            continue
        word = "over" if b.over else "near"
        out.append(
            Candidate(
                type="budget_alert",
                entity_key=f"budget:{b.category}",
                features={"over_ratio": float(b.actual / b.limit) if b.limit else 0.0},
                provenance=Provenance(
                    generator="budget_threshold",
                    reason=f"Budget '{b.category}' is {word}: spent {b.actual} of {b.limit}.",
                    source_ids=[f"budget:{b.category}"],
                ),
                payload={
                    "category": b.category,
                    "limit": str(b.limit),
                    "actual": str(b.actual),
                    "remaining": str(b.remaining),
                    "over": b.over,
                },
            )
        )
    return out


def recurring_bill_due(state: EngineState) -> list[Candidate]:
    """A detected subscription whose next charge (last seen + cadence) falls within the horizon."""
    if not state.transactions:
        return []
    today = _aware(state.now).date()
    horizon = config.recurring_horizon_days
    last_seen: dict[str, date] = {}
    for t in state.transactions:
        if t.amount < 0 and (t.merchant not in last_seen or t.date > last_seen[t.merchant]):
            last_seen[t.merchant] = t.date
    out = []
    for rec in recurring_charges(state.transactions):
        cadence_days = _CADENCE_DAYS.get(rec.cadence)
        last = last_seen.get(rec.merchant)
        if cadence_days is None or last is None:
            continue
        due = last + timedelta(days=cadence_days)
        days_until = (due - today).days
        if not 0 <= days_until <= horizon:
            continue
        out.append(
            Candidate(
                type="followup_due",
                entity_key=f"recurring:{rec.merchant}",
                features={"days_until": float(days_until)},
                provenance=Provenance(
                    generator="recurring_bill_due",
                    reason=f"{rec.merchant} (~{rec.amount}) is due in {days_until} day(s).",
                    source_ids=[f"recurring:{rec.merchant}"],
                ),
                payload={
                    "merchant": rec.merchant,
                    "amount": str(rec.amount),
                    "cadence": rec.cadence,
                    "due": due.isoformat(),
                },
            )
        )
    return out


def event_prep(state: EngineState) -> list[Candidate]:
    """An upcoming timed calendar event within the horizon -> a prep / block-focus-time nudge."""
    horizon = timedelta(hours=config.urgency_horizon_hours)
    now = _aware(state.now)
    out = []
    for e in state.events:
        if e.all_day:
            continue
        start = _aware(e.start)
        if not now <= start <= now + horizon:
            continue
        hours = (start - now).total_seconds() / 3600.0
        out.append(
            Candidate(
                type="free_time",
                entity_key=f"event:{e.id}",
                features={"start_hours": hours},
                provenance=Provenance(
                    generator="event_prep",
                    reason=f"'{e.summary}' starts in {_days_or_hours(hours)}; prep or block focus.",
                    source_ids=[f"event:{e.id}"],
                ),
                payload={"summary": e.summary, "start": start.isoformat(), "location": e.location},
            )
        )
    return out


# Registry order matters: an earlier generator wins a shared entity_key in generate_all.
GENERATORS = [goal_deadline, stale_goal, budget_threshold, recurring_bill_due, event_prep]


def generate_all(state: EngineState, generators=None) -> list[Candidate]:
    """Union every generator's candidates, dedup by entity_key (first generator wins)."""
    gens = GENERATORS if generators is None else generators
    seen: set[str] = set()
    out: list[Candidate] = []
    for gen in gens:
        for candidate in gen(state):
            if candidate.entity_key in seen:
                continue
            seen.add(candidate.entity_key)
            out.append(candidate)
    return out
