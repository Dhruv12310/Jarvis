"""Feedback (Core §7.5) - the reward that closes the loop, and the ONE place §8 is enforced.

The reward measures GENUINE value, never attention. Explicit "helpful" (more_like_this) is the gold
signal; `acted` counts ONLY when corroborated by a real good outcome (a goal advanced, a miss
prevented) - `acted` alone is non-positive, because a tap is a choice, not a confirmed value. A
dismissal is a negative; `ignored` (and any bare shown/dwell) is neutral and can NEVER be positive.
This module is deterministic - no LLM, no attention input - and a test pins these semantics.
"""

from __future__ import annotations

# The outcome vocabulary (Core §5.5).
RESULTS = ("acted", "dismissed", "ignored", "more_like_this", "less_like_this")


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
