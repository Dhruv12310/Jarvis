"""Reflection context: deterministic aggregation of signals/memories/goals into the exact block the
LLM may see (injected now + injected memories -> pure, byte-for-byte reproducible)."""

from datetime import UTC, datetime
from types import SimpleNamespace

from jarvis.proactivity.context import build_context


def _sig(kind, hour, source="cli"):
    return SimpleNamespace(
        kind=kind, ts=datetime(2026, 6, 1, hour, tzinfo=UTC), payload={"source": source}
    )


def _mem(mem_id, content):
    return SimpleNamespace(id=mem_id, content=content)


def test_build_context_aggregates_signals_memories_goals_deterministically():
    now = datetime(2026, 6, 3, 9, 0)
    signals = [_sig("ask", 9), _sig("ask", 9), _sig("goal_done", 14)]
    memories = [_mem("m1", "I want to learn rust")]
    goals = [SimpleNamespace(description="ship phase 5")]

    ctx = build_context(signals, memories, goals, now=now)

    assert "by kind: ask=2, goal_done=1" in ctx.block
    assert "by hour: 09h=2, 14h=1" in ctx.block
    assert "[m1] I want to learn rust" in ctx.block
    assert "ship phase 5" in ctx.block
    assert ctx.source_ids == frozenset({"m1", "signals"})
    # Pure: same inputs (incl. injected now) -> identical block.
    assert build_context(signals, memories, goals, now=now).block == ctx.block


def test_empty_context_is_handled():
    ctx = build_context([], [], [], now=datetime(2026, 6, 3, 9, 0))

    assert "(none)" in ctx.block
    assert ctx.source_ids == frozenset(
        {"signals"}
    )  # a behavioral insight may still ground on "signals"
