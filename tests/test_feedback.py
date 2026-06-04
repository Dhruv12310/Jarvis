"""Feedback (§7.5) - the §8 contract made code: genuine value, never attention; and applying an
outcome to the user model + the learned ranker weights."""

from datetime import UTC, datetime
from types import SimpleNamespace

from jarvis.proactivity import user_model as um
from jarvis.proactivity.feedback import apply_outcome, reward, value_metric
from jarvis.proactivity.user_model import UserModel
from jarvis.stores.sqlite_store import SQLiteStructuredStore
from jarvis.stores.structured import Outcome, Suggestion

NOW = datetime(2026, 6, 4, 9, 0, tzinfo=UTC)
_A = _G = 0.3
_LR = 0.1


def _sugg(*, topics, features=None):
    return Suggestion(
        id="s1",
        created_at=NOW,
        candidate_type="goal_nudge",
        entity_key="goal:1",
        content="x",
        why="y",
        source_ids=["goal:1"],
        topics=topics,
        features=features or {"goal": 1.0, "urgency": 1.0},
        score=2.0,
        surfaced=True,
        channel="feed",
    )


def _goal(desc="learn rust"):
    return SimpleNamespace(id=1, description=desc, priority="high", status="active")


def test_reward_encodes_value_never_attention():
    assert reward("more_like_this") == 1.0  # explicit helpful is positive
    assert reward("acted") == 0.0  # §8: acted ALONE is non-positive (a tap is not confirmed value)
    assert reward("acted", corroborated=True) > 0  # corroborated by a real good outcome -> positive
    assert reward("dismissed") < 0
    assert reward("less_like_this") < 0
    assert reward("ignored") == 0.0  # neutral - attention is never a positive reward


def test_outcome_store_round_trips(tmp_path):
    store = SQLiteStructuredStore(tmp_path / "j.db")
    ts = datetime(2026, 6, 4, 9, 0, tzinfo=UTC)
    store.save_outcome(Outcome(suggestion_id="abc", ts=ts, result="more_like_this"))
    store.save_outcome(Outcome(suggestion_id="def", ts=ts, result="dismissed"))

    outcomes = store.get_outcomes()

    assert {(o.suggestion_id, o.result) for o in outcomes} == {
        ("abc", "more_like_this"),
        ("def", "dismissed"),
    }


def test_positive_outcome_amplifies_goal_linked_topic_and_driving_features():
    out = Outcome("s1", NOW, "more_like_this")

    model, weights = apply_outcome(
        out,
        _sugg(topics=["rust"]),
        UserModel(),
        {},
        [_goal("learn rust")],
        now=NOW,
        alpha=_A,
        gamma=_G,
        lr=_LR,
    )

    rust = next(i for i in model.interests if i.topic == "rust")
    assert rust.weight > 0  # goal-linked topic amplified
    assert (
        weights["goal"] > 1.0 and weights["urgency"] > 1.0
    )  # the features that drove it reinforced


def test_acted_alone_is_non_positive_and_changes_nothing():
    out = Outcome("s1", NOW, "acted")  # reward 0 (no corroboration)

    model, weights = apply_outcome(
        out,
        _sugg(topics=["rust"]),
        UserModel(),
        {},
        [_goal()],
        now=NOW,
        alpha=_A,
        gamma=_G,
        lr=_LR,
    )

    assert model.interests == []  # nothing amplified
    assert weights == {}  # no weight movement - §8: a tap is not value


def test_dismissed_outcome_suppresses_topic_and_attenuates_features():
    seeded = um.reinforce_interest(
        UserModel(), "rust", [_goal("learn rust")], now=NOW, alpha=_A, gamma=_G
    )
    w0 = next(i for i in seeded.interests if i.topic == "rust").weight
    out = Outcome("s1", NOW, "dismissed")

    model, weights = apply_outcome(
        out,
        _sugg(topics=["rust"]),
        seeded,
        {"goal": 1.2},
        [_goal("learn rust")],
        now=NOW,
        alpha=_A,
        gamma=_G,
        lr=_LR,
    )

    assert next(i for i in model.interests if i.topic == "rust").weight < w0  # suppressed
    assert weights["goal"] < 1.2 and weights["urgency"] < 1.0  # driving features attenuated


def test_positive_outcome_cannot_amplify_a_non_goal_topic():
    # §8: even explicit "helpful" cannot give a non-goal-linked (pure-frequency) topic a weight.
    out = Outcome("s1", NOW, "more_like_this")

    model, _ = apply_outcome(
        out,
        _sugg(topics=["crypto"]),
        UserModel(),
        {},
        [_goal("learn rust")],
        now=NOW,
        alpha=_A,
        gamma=_G,
        lr=_LR,
    )

    crypto = next(i for i in model.interests if i.topic == "crypto")
    assert crypto.weight == 0.0


def test_objective_is_usefulness_not_engagement():
    # THE capstone (§8): an attention outcome (ignored) moves NO weight; explicit value does.
    sugg = _sugg(topics=["rust"])
    _, w_ignored = apply_outcome(
        Outcome("s1", NOW, "ignored"),
        sugg,
        UserModel(),
        {},
        [_goal()],
        now=NOW,
        alpha=_A,
        gamma=_G,
        lr=_LR,
    )
    _, w_helpful = apply_outcome(
        Outcome("s1", NOW, "more_like_this"),
        sugg,
        UserModel(),
        {},
        [_goal()],
        now=NOW,
        alpha=_A,
        gamma=_G,
        lr=_LR,
    )

    assert w_ignored == {}  # attention -> no learning whatsoever
    assert w_helpful and all(v > 1.0 for v in w_helpful.values())  # genuine value -> reinforced


def test_value_metric_measures_helpfulness_and_excludes_attention():
    outcomes = [
        SimpleNamespace(result="more_like_this"),
        SimpleNamespace(result="dismissed"),
        SimpleNamespace(result="ignored"),  # attention - excluded from the denominator
        SimpleNamespace(result="ignored"),
    ]
    assert value_metric(outcomes) == 0.5  # 1 helpful of 2 value-bearing; the 2 ignored don't count
    assert value_metric([]) == 0.0
