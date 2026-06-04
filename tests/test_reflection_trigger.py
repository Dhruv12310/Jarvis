"""Reflection trigger (§7.4): deterministic per-kind fuel, the attention denylist, accumulation, and
the threshold. No LLM, no clock - pure functions.
"""

from types import SimpleNamespace

from jarvis.proactivity.trigger import accumulated_fuel, should_reflect
from jarvis.proactivity.trigger_weights import DENYLIST, trigger_fuel


def _sig(kind):
    return SimpleNamespace(kind=kind)


def test_trigger_fuel_is_deterministic_per_kind():
    assert trigger_fuel("goal_done") == 1.0  # a declared milestone
    assert trigger_fuel("goal_list") == 0.1  # an inspector
    assert trigger_fuel("totally_unknown_kind") == 0.2  # default


def test_attention_kinds_yield_zero_fuel():
    # Core §8 made code: a passive view/dwell can NEVER drive the learning loop.
    assert "item_dwell" in DENYLIST and "suggestion_shown" in DENYLIST
    for kind in DENYLIST:
        assert trigger_fuel(kind) == 0.0


def test_self_referential_meta_kinds_yield_zero_fuel():
    # Running/inspecting/controlling the model must not fuel more reflection - e.g. a reflection's
    # own emitted signal can't bootstrap the next one into a self-sustaining loop.
    for kind in ("reflect", "user_model", "user_model_reset", "forget", "suppress_topic"):
        assert trigger_fuel(kind) == 0.0


def test_accumulated_fuel_sums_and_excludes_attention():
    signals = [_sig("goal_done"), _sig("ask"), _sig("item_dwell")]  # 1.0 + 0.4 + 0.0

    assert accumulated_fuel(signals) == 1.4


def test_should_reflect_fires_at_the_threshold():
    assert should_reflect(5.0, 5.0) is True
    assert should_reflect(4.9, 5.0) is False
