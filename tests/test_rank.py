"""The §7.2 ranker + gate: exact weighted sum + contributions; absolute-threshold abstention; the
structural frequency cap; per-category cap; per-entity cooldown; the DND gate; top-K ordering.
The §8 guards live here: a weak pool surfaces NOTHING, and volume is capped regardless of score."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from pytest import approx

from jarvis.config import Config, config
from jarvis.proactivity import rank
from jarvis.proactivity.candidate import Candidate, EngineState, Provenance
from jarvis.proactivity.user_model import Interest, UserModel

NOW = datetime(2026, 6, 3, 9, 0, tzinfo=UTC)  # 09:00 - outside the default quiet hours (22-07)


def _cand(*, ctype="goal_nudge", entity_key="goal:1", features=None, topics=()):
    return Candidate(
        type=ctype,
        entity_key=entity_key,
        features=features or {},
        provenance=Provenance("g", "why", [entity_key]),
        payload={},
        topics=list(topics),
    )


def _goal(gid=1, *, description="learn rust", priority="high"):
    return SimpleNamespace(id=gid, description=description, priority=priority, status="active")


def _state(goals=None, *, now=NOW, interests=(), recent=()):
    return EngineState(
        now=now,
        goals=goals or [],
        user_model=UserModel(interests=list(interests)),
        recent_suggestions=list(recent),
    )


def test_usefulness_equals_weighted_sum_and_contributions_sum_to_score():
    cand = _cand(entity_key="goal:1", features={"deadline_hours": 0.0}, topics=["rust"])
    state = _state(
        [_goal(1, description="learn rust", priority="high")],
        interests=[Interest("rust", 0.5, 0.5, NOW)],
    )

    score, contrib = rank.usefulness(cand, state)

    # goal=1.0, urgency=1.0, interest=0.5, timing=1.0, novelty=1.0, fatigue=0
    expected = (
        config.beta_goal * 1.0
        + config.beta_urgency * 1.0
        + config.beta_interest * 0.5
        + config.beta_timing * 1.0
        + config.beta_novelty * 1.0
    )
    assert score == approx(expected)
    assert sum(contrib.values()) == approx(score)


def test_learned_feedback_weights_scale_the_score():
    cand = _cand(entity_key="goal:1", features={"deadline_hours": 0.0})
    base, _ = rank.usefulness(cand, _state([_goal()]))
    boosted, _ = rank.usefulness(
        cand,
        EngineState(
            now=NOW, goals=[_goal()], user_model=UserModel(), feedback_weights={"urgency": 2.0}
        ),
    )

    assert boosted > base  # a learned multiplier shifts the score (and thus future ranking)


def test_weak_pool_surfaces_nothing():
    # A bare news candidate - no goal, no interest, no urgency - falls below the absolute threshold.
    weak = _cand(ctype="news", entity_key="news:1", topics=["celebrity gossip"])

    assert rank.select([weak], _state([])) == []


def test_structural_cap_bounds_volume_regardless_of_scores():
    # Five distinct-type candidates, all well above threshold -> capped to suggestions_per_window.
    types = ["goal_nudge", "budget_alert", "followup_due", "free_time", "market_move"]
    cands = [_cand(ctype=t, entity_key=f"{t}:1", features={"deadline_hours": 0.0}) for t in types]

    out = rank.select(cands, _state([]))

    assert len(out) == config.suggestions_per_window  # 3, not 5 - volume is structurally bounded


def test_per_category_cap_limits_one_type():
    cands = [
        _cand(entity_key=f"goal:{i}", features={"deadline_hours": 0.0}) for i in range(3)
    ]  # all goal_nudge, all above threshold

    out = rank.select(cands, _state([]))

    assert len(out) == config.per_category_cap  # 1


def test_top_k_is_ordered_by_score_descending():
    high = _cand(
        entity_key="budget_alert:1",
        ctype="budget_alert",
        features={"deadline_hours": 0.0},
        topics=["learn rust"],
    )
    low = _cand(entity_key="market_move:1", ctype="market_move", features={"deadline_hours": 12.0})
    state = _state([_goal(1, description="learn rust", priority="high")])

    out = rank.select([low, high], state)

    assert [s.candidate.entity_key for s in out] == ["budget_alert:1", "market_move:1"]
    assert out[0].score > out[1].score


def test_entity_cooldown_excludes_recently_surfaced():
    cand = _cand(entity_key="goal:1", features={"deadline_hours": 0.0})
    # 30h ago: inside the 48h cooldown but outside the 24h fatigue window, so it WOULD score high.
    recent = [SimpleNamespace(entity_key="goal:1", created_at=NOW - timedelta(hours=30))]

    assert rank.select([cand], _state([], recent=recent)) == []
    assert len(rank.select([cand], _state([]))) == 1  # same candidate surfaces with no cooldown


def test_dnd_gate_suppresses_all_in_quiet_hours():
    cand = _cand(entity_key="goal:1", features={"deadline_hours": 0.0})

    assert rank.select([cand], _state([], now=NOW.replace(hour=1))) == []  # 01:00 is quiet


def test_dnd_gate_suppresses_all_when_proactivity_disabled(monkeypatch):
    monkeypatch.setenv("JARVIS_PROACTIVITY_ENABLED", "0")
    monkeypatch.setattr(rank, "config", Config())  # re-read env into a fresh config
    cand = _cand(entity_key="goal:1", features={"deadline_hours": 0.0})

    assert rank.select([cand], _state([])) == []
