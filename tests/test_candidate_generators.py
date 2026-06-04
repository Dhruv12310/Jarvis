"""Owned-data candidate generators (Core Stage 6, generation). Each fires on the right state and
abstains otherwise; provenance resolves to real source ids; generate_all dedups by entity_key.
Pure - generators read an injected EngineState only, never the facade/HTTP/LLM/clock.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from jarvis.calendar.client import CalendarEvent
from jarvis.finance.transaction import BudgetStatus, Transaction
from jarvis.proactivity import candidate as cand_mod
from jarvis.proactivity import generators as gens_mod
from jarvis.proactivity.candidate import EngineState
from jarvis.proactivity.generators import (
    budget_threshold,
    event_prep,
    generate_all,
    goal_deadline,
    recurring_bill_due,
    stale_goal,
)
from jarvis.stores.structured import Goal

NOW = datetime(2026, 6, 3, 9, 0, tzinfo=UTC)


def _goal(gid, *, deadline=None, progress=0.0, status="active", created=NOW, desc="ship 5b"):
    return Goal(
        id=gid,
        description=desc,
        status=status,
        progress=progress,
        priority="medium",
        deadline=deadline,
        created_at=created,
    )


def _txn(day, *, merchant="Netflix", amount="-15.99"):
    return Transaction(
        id=f"{merchant}-{day}",
        date=day,
        amount=Decimal(amount),
        merchant=merchant,
        category="subscriptions",
        account="checking",
    )


def _event(eid, start, *, all_day=False, summary="Dentist"):
    return CalendarEvent(
        id=eid,
        summary=summary,
        start=start,
        end=start + timedelta(hours=1),
        location=None,
        all_day=all_day,
    )


# --- goal_deadline ---------------------------------------------------------------------


def test_goal_deadline_fires_within_horizon_and_abstains_outside():
    near = _goal(7, deadline=NOW + timedelta(days=2))
    far = _goal(8, deadline=NOW + timedelta(days=30))
    undated = _goal(9, deadline=None)
    state = EngineState(now=NOW, goals=[near, far, undated])

    out = goal_deadline(state)

    assert [c.entity_key for c in out] == ["goal:7"]
    assert out[0].type == "goal_nudge"
    assert out[0].provenance.source_ids == ["goal:7"]
    assert out[0].provenance.reason  # non-empty deterministic "why"


# --- stale_goal ------------------------------------------------------------------------


def test_stale_goal_fires_for_old_low_progress_and_abstains_for_fresh():
    stale = _goal(1, created=NOW - timedelta(days=30), progress=0.1)
    fresh = _goal(2, created=NOW - timedelta(days=1), progress=0.1)
    state = EngineState(now=NOW, goals=[stale, fresh])

    out = stale_goal(state)

    assert [c.entity_key for c in out] == ["goal:1"]


def test_stale_goal_defers_to_goal_deadline_when_deadline_is_near():
    g = _goal(1, created=NOW - timedelta(days=30), progress=0.1, deadline=NOW + timedelta(days=1))

    out = stale_goal(EngineState(now=NOW, goals=[g]))

    assert out == []  # a near-deadline goal belongs to goal_deadline (dedup at the source)


# --- budget_threshold ------------------------------------------------------------------


def test_budget_threshold_fires_over_and_near_abstains_healthy():
    over = BudgetStatus(
        category="dining",
        limit=Decimal("200"),
        actual=Decimal("250"),
        remaining=Decimal("-50"),
        over=True,
    )
    near = BudgetStatus(
        category="grocery",
        limit=Decimal("400"),
        actual=Decimal("390"),
        remaining=Decimal("10"),
        over=False,
    )
    healthy = BudgetStatus(
        category="transport",
        limit=Decimal("100"),
        actual=Decimal("20"),
        remaining=Decimal("80"),
        over=False,
    )
    state = EngineState(now=NOW, budget_status=[over, near, healthy])

    out = budget_threshold(state)

    assert {c.entity_key for c in out} == {"budget:dining", "budget:grocery"}
    assert all(c.type == "budget_alert" for c in out)


# --- recurring_bill_due ----------------------------------------------------------------


def test_recurring_bill_due_fires_when_next_charge_is_soon():
    txns = [_txn(date(2026, 3, 5)), _txn(date(2026, 4, 5)), _txn(date(2026, 5, 5))]

    out = recurring_bill_due(EngineState(now=NOW, transactions=txns))

    assert [c.entity_key for c in out] == ["recurring:Netflix"]  # next ~2026-06-04, due soon


def test_recurring_bill_due_abstains_when_next_charge_is_far():
    txns = [_txn(date(2026, 4, 3)), _txn(date(2026, 5, 3)), _txn(date(2026, 6, 1))]

    out = recurring_bill_due(EngineState(now=NOW, transactions=txns))

    assert out == []  # last charge 06-01 -> next ~07-01, far beyond the horizon


# --- event_prep ------------------------------------------------------------------------


def test_event_prep_fires_for_timed_event_in_horizon_and_skips_all_day_and_far():
    soon = _event("e1", NOW + timedelta(hours=3))
    allday = _event("e2", NOW + timedelta(hours=2), all_day=True)
    far = _event("e3", NOW + timedelta(days=10))
    state = EngineState(now=NOW, events=[soon, allday, far])

    out = event_prep(state)

    assert [c.entity_key for c in out] == ["event:e1"]
    assert out[0].type == "free_time"


# --- generate_all dedup ----------------------------------------------------------------


def test_generate_all_unions_and_dedups_by_entity_key():
    # A goal both near-deadline and old: goal_deadline (first in the registry) must win.
    g = _goal(7, created=NOW - timedelta(days=30), progress=0.1, deadline=NOW + timedelta(days=2))
    over = BudgetStatus(
        category="dining",
        limit=Decimal("200"),
        actual=Decimal("250"),
        remaining=Decimal("-50"),
        over=True,
    )
    state = EngineState(now=NOW, goals=[g], budget_status=[over])

    out = generate_all(state)

    keys = [c.entity_key for c in out]
    assert keys.count("goal:7") == 1  # deduped to a single card
    assert "budget:dining" in keys
    goal_card = next(c for c in out if c.entity_key == "goal:7")
    assert goal_card.provenance.generator == "goal_deadline"


# --- purity ----------------------------------------------------------------------------


def test_generators_are_pure_no_io_imports():
    for mod in (gens_mod, cand_mod):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "import httpx",
            "ollama",
            "from jarvis.service",
            "JarvisService",
            "LLMClient",
        ):
            assert forbidden not in src, f"{mod.__name__} must stay pure ({forbidden})"


def test_generators_take_only_injected_state():
    # An empty snapshot yields nothing and raises nothing - generators read state, not the world.
    empty = EngineState(now=NOW)
    for gen in (goal_deadline, stale_goal, budget_threshold, recurring_bill_due, event_prep):
        assert gen(empty) == []
