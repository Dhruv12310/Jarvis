"""§7.4 reflection trigger: fire reflection when accumulated deterministic FUEL since the last
reflection crosses the threshold. Pure functions - no LLM, no clock, no I/O - fully testable.

The caller fetches the signals after the last-processed `seq` baseline (durable, monotonic) and
feeds them here; on a successful reflection it advances the baseline to the latest seq.
"""

from __future__ import annotations

from jarvis.proactivity.trigger_weights import trigger_fuel


def accumulated_fuel(signals) -> float:
    """Sum the deterministic trigger fuel of the signals since the last reflection."""
    return sum(trigger_fuel(s.kind) for s in signals)


def should_reflect(accumulated: float, threshold: float) -> bool:
    return accumulated >= threshold
