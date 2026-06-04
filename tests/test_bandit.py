"""Per-category explore/exploit (§7.3): pessimistic posterior, deterministic UCB multiplier, and the
exponential-backoff dismissal cooldown. Pure - no randomness, no LLM."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from jarvis.proactivity import bandit

NOW = datetime(2026, 6, 4, 9, 0, tzinfo=UTC)


def _o(category, result, ts=NOW):
    return SimpleNamespace(category=category, result=result, ts=ts)


def test_untried_category_uses_pessimistic_prior():
    assert bandit.value_estimate("market_move", []) == 0.25  # Beta(1,3) mean, not 0.5


def test_value_estimate_rises_with_positive_outcomes():
    helpful = [_o("goal_nudge", "more_like_this") for _ in range(5)]
    assert bandit.value_estimate("goal_nudge", helpful) > 0.5


def test_proven_category_outranks_chronically_dismissed_at_equal_base_score():
    history = [_o("goal_nudge", "more_like_this") for _ in range(6)]
    history += [_o("market_move", "dismissed") for _ in range(6)]

    assert bandit.category_multiplier("goal_nudge", history) > bandit.category_multiplier(
        "market_move", history
    )


def test_untried_category_gets_an_exploration_lift_over_a_dismissed_one():
    history = [_o("market_move", "dismissed") for _ in range(5)]
    # an untried category should not be buried below a repeatedly-dismissed one
    assert bandit.category_multiplier("yc_launch", history) > bandit.category_multiplier(
        "market_move", history
    )


def test_multiplier_never_exceeds_the_band():
    great = [_o("goal_nudge", "more_like_this") for _ in range(50)]
    assert bandit.category_multiplier("goal_nudge", great) <= 1.3


def test_consecutive_dismissals_lengthen_the_cooldown():
    one = [_o("market_move", "dismissed", NOW - timedelta(days=2))]
    three = [_o("market_move", "dismissed", NOW - timedelta(days=2)) for _ in range(3)]

    # base 1 day: after one dismissal 2 days ago the cooldown has lapsed...
    assert not bandit.cooldown_active("market_move", one, NOW, base_days=1, cap_days=30)
    # ...but three consecutive dismissals back it off to 1*2^2 = 4 days, so it is still active.
    assert bandit.cooldown_active("market_move", three, NOW, base_days=1, cap_days=30)


def test_a_recent_helpful_breaks_the_dismissal_streak():
    history = [
        _o("market_move", "more_like_this", NOW - timedelta(hours=1)),
        _o("market_move", "dismissed", NOW - timedelta(days=1)),
        _o("market_move", "dismissed", NOW - timedelta(days=2)),
    ]
    # the most recent outcome is helpful -> no trailing dismissal streak -> no cooldown
    assert not bandit.cooldown_active("market_move", history, NOW, base_days=1, cap_days=30)
