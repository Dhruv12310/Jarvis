"""User model: the pinned confidence math, the Core §8 guard (pure frequency never amplifies an
interest weight - only goal-linked topics do), and serialization. Deterministic, no LLM.
"""

from datetime import datetime
from types import SimpleNamespace

from pytest import approx

from jarvis.proactivity.reflect import Insight
from jarvis.proactivity.user_model import (
    UserModel,
    confidence_after,
    from_dict,
    merge,
    suppress_interest,
    to_dict,
)

NOW = datetime(2026, 6, 3, 9, 0)
_A = _G = 0.3  # alpha = gamma for the tests


def _interest(topic):
    return Insight(kind="interest", content=f"keeps using {topic}", links=["signals"], topic=topic)


def test_confidence_after_is_a_pinned_pure_function():
    assert confidence_after(0.0, "confirm", alpha=_A, gamma=_G) == approx(0.3)
    assert confidence_after(0.5, "confirm", alpha=_A, gamma=_G) == approx(0.65)  # 0.5 + 0.3*0.5
    assert confidence_after(0.5, "contradict", alpha=_A, gamma=_G) == approx(0.35)  # 0.5 - 0.3*0.5
    assert confidence_after(1.0, "confirm", alpha=_A, gamma=_G) == 1.0  # clamp
    assert confidence_after(0.0, "contradict", alpha=_A, gamma=_G) == 0.0  # clamp


def test_confidence_rises_on_reconfirm_and_decays_on_contradiction():
    c = 0.5
    assert (
        confidence_after(c, "confirm", alpha=_A, gamma=_G)
        > c
        > confidence_after(c, "contradict", alpha=_A, gamma=_G)
    )


def test_goal_linked_interest_amplifies_but_pure_frequency_does_not():
    goals = [SimpleNamespace(description="learn rust")]
    model = UserModel()

    model = merge(model, _interest("rust"), goals, now=NOW, alpha=_A, gamma=_G)
    model = merge(model, _interest("crypto"), goals, now=NOW, alpha=_A, gamma=_G)

    by_topic = {i.topic: i for i in model.interests}
    assert by_topic["rust"].weight == 0.3  # goal-linked -> amplified
    assert by_topic["crypto"].weight == 0.0  # pure frequency -> NEVER amplified (Core §8)
    assert by_topic["crypto"].confidence == 0.3  # ...but the pattern is still recorded


def test_reconfirming_an_interest_raises_confidence():
    goals = [SimpleNamespace(description="learn rust")]
    model = merge(UserModel(), _interest("rust"), goals, now=NOW, alpha=_A, gamma=_G)

    model = merge(model, _interest("rust"), goals, now=NOW, alpha=_A, gamma=_G)

    rust = [i for i in model.interests if i.topic == "rust"][0]
    assert rust.confidence == approx(confidence_after(0.3, "confirm", alpha=_A, gamma=_G))


def test_suppress_interest_decays_weight_and_confidence():
    goals = [SimpleNamespace(description="learn rust")]
    model = merge(UserModel(), _interest("rust"), goals, now=NOW, alpha=_A, gamma=_G)

    model = suppress_interest(model, "rust", now=NOW, gamma=_G)

    rust = [i for i in model.interests if i.topic == "rust"][0]
    assert rust.weight < 0.3 and rust.confidence < 0.3


def test_rhythm_merge_confirms():
    model = merge(
        UserModel(),
        Insight(kind="rhythm", content="works in the morning", links=["signals"]),
        [],
        now=NOW,
        alpha=_A,
        gamma=_G,
    )
    assert model.rhythms[0].pattern == "works in the morning"


def test_to_from_dict_round_trips():
    model = merge(
        UserModel(),
        _interest("rust"),
        [SimpleNamespace(description="learn rust")],
        now=NOW,
        alpha=_A,
        gamma=_G,
    )

    restored = from_dict(to_dict(model))

    assert restored.interests[0].topic == "rust"
    assert restored.interests[0].weight == model.interests[0].weight
