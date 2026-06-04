"""Ranking features (Core §7.2): each calibrated [0,1] and monotone, and - the §8 guard -
interest_match returns 0 for a pure-frequency (non-goal-linked) interest. Pure, no LLM/HTTP."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from pytest import approx

from jarvis.proactivity import features as F
from jarvis.proactivity.candidate import Candidate, Provenance

NOW = datetime(2026, 6, 3, 9, 0, tzinfo=UTC)


def _cand(*, ctype="goal_nudge", entity_key="goal:1", features=None, topics=()):
    return Candidate(
        type=ctype,
        entity_key=entity_key,
        features=features or {},
        provenance=Provenance("g", "why", [entity_key]),
        payload={},
        topics=list(topics),
    )


def _goal(gid=1, *, description="learn rust", priority="high", status="active"):
    return SimpleNamespace(id=gid, description=description, priority=priority, status=status)


def test_goal_relevance_grades_by_priority_and_matches_topic():
    assert F.goal_relevance(_cand(entity_key="goal:1"), [_goal(priority="high")]) == 1.0
    low = _goal(gid=2, priority="low", description="read more books")
    assert F.goal_relevance(_cand(entity_key="goal:9", topics=["read more books"]), [low]) == 0.3
    assert F.goal_relevance(_cand(entity_key="goal:9", topics=["unrelated"]), [_goal()]) == 0.0


def test_urgency_is_monotone_decreasing_in_time_to_deadline():
    due_now = F.urgency(_cand(features={"deadline_hours": 0.0}), horizon_hours=72)
    soon = F.urgency(_cand(features={"deadline_hours": 24.0}), horizon_hours=72)
    far = F.urgency(_cand(features={"deadline_hours": 72.0}), horizon_hours=72)
    assert due_now == 1.0
    assert due_now > soon > far == approx(0.0)


def test_interest_match_is_zero_for_pure_frequency_interest():
    # §8: weight is 0.0 for a non-goal-linked interest, so a compulsion contributes NOTHING.
    compulsion = SimpleNamespace(topic="crypto", weight=0.0)
    goal_linked = SimpleNamespace(topic="rust", weight=0.7)
    assert F.interest_match(_cand(topics=["crypto"]), [compulsion]) == 0.0
    assert F.interest_match(_cand(topics=["rust"]), [goal_linked]) == 0.7


def test_timing_fit_is_zero_in_quiet_hours():
    assert F.timing_fit(NOW, [], quiet_hours=(22, 7)) == 1.0  # 09:00 is fine
    assert F.timing_fit(NOW.replace(hour=1), [], quiet_hours=(22, 7)) == 0.0  # 01:00 is quiet


def test_novelty_rises_as_time_since_last_surface_grows():
    shown_now = [SimpleNamespace(entity_key="goal:1", created_at=NOW)]
    shown_long_ago = [SimpleNamespace(entity_key="goal:1", created_at=NOW - timedelta(days=10))]
    fresh = F.novelty(_cand(entity_key="goal:1"), [], now=NOW, lam=0.02)
    just_shown = F.novelty(_cand(entity_key="goal:1"), shown_now, now=NOW, lam=0.02)
    old = F.novelty(_cand(entity_key="goal:1"), shown_long_ago, now=NOW, lam=0.02)
    assert fresh == 1.0
    assert just_shown == approx(0.0)
    assert old > just_shown


def test_recent_interruption_penalty_saturates_at_cap():
    recent = [SimpleNamespace(entity_key="x", created_at=NOW) for _ in range(5)]
    assert F.recent_interruption_penalty(recent, now=NOW, window_hours=24, cap=3) == 1.0
    assert F.recent_interruption_penalty([], now=NOW, window_hours=24, cap=3) == 0.0
