"""Feedback (Core §7.5) - the reward that closes the loop, and the ONE place §8 is enforced.

The reward measures GENUINE value, never attention. Explicit "helpful" (more_like_this) is the gold
signal; `acted` counts ONLY when corroborated by a real good outcome (a goal advanced, a miss
prevented) - `acted` alone is non-positive, because a tap is a choice, not a confirmed value. A
dismissal is a negative; `ignored` (and any bare shown/dwell) is neutral and can NEVER be positive.
This module is deterministic - no LLM, no attention input - and a test pins these semantics.
"""

from __future__ import annotations

from jarvis.proactivity import user_model as um

# The outcome vocabulary (Core §5.5).
RESULTS = ("acted", "dismissed", "ignored", "more_like_this", "less_like_this")

# Bounds on a learned ranker weight multiplier. Feedback can tune a feature within this band but
# never silence it or let it dominate - the hand-set base weights stay the anchor.
_WEIGHT_LO, _WEIGHT_HI = 0.5, 2.0


def reward(result: str, *, corroborated: bool = False) -> float:
    """Value of an outcome in [-1, 1]. §8: attention is never positive; `acted` needs proof."""
    if result == "more_like_this":
        return 1.0  # explicit helpful - the strongest value signal we can get
    if result == "acted":
        return 0.5 if corroborated else 0.0  # a tap alone is NOT confirmed value
    if result == "less_like_this":
        return -1.0
    if result == "dismissed":
        return -0.5
    return 0.0  # ignored / unknown - neutral; never a positive reward


def update_weights(weights: dict, contributions: dict, r: float, *, lr: float) -> dict:
    """Nudge the learned multiplier of each feature that DROVE this suggestion, in the direction of
    the reward and scaled by its MAGNITUDE (not a flat per-event count). Only features that
    contributed positively are credited; `fatigue` is a penalty, never reinforced. Clamped."""
    if r == 0:
        return weights
    updated = dict(weights)
    for feature, contribution in contributions.items():
        if feature == "fatigue" or contribution <= 0:
            continue
        nudged = updated.get(feature, 1.0) + lr * r
        updated[feature] = max(_WEIGHT_LO, min(_WEIGHT_HI, nudged))
    return updated


def apply_outcome(outcome, suggestion, model, weights, goals, *, now, alpha, gamma, lr):
    """Fold one outcome into the user model + the learned ranker weights (Core §7.5). Returns the
    new (model, weights). Positive value amplifies a GOAL-LINKED topic (the §8 guard keeps a
    pure-frequency topic at weight 0.0); a negative outcome suppresses the topic. The feature
    weights move only for genuine value - an `acted`-alone (reward 0) changes nothing."""
    r = reward(outcome.result)
    for topic in suggestion.topics:
        if r > 0:
            model = um.reinforce_interest(
                model, topic, goals, now=now, alpha=alpha * r, gamma=gamma
            )
        elif r < 0:
            model = um.suppress_interest(model, topic, now=now, gamma=gamma * -r)
    weights = update_weights(weights, suggestion.features, r, lr=lr)
    return model, weights
