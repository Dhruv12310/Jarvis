"""Deterministic reflection context (Stage 4 input). Code aggregates; the LLM only synthesizes it.

The block the LLM may see is built ENTIRELY here, from: the signal log (metadata-only -> rhythms /
cadence / modality / time-of-day; the log has NO topics), the user's EXPLICIT memories (their own
content, the grounding for interests/preferences), and active goals. It is redacted before it goes.
`build_context` takes an injected `now` and an already-retrieved memory list so it is pure - the
byte-for-byte grounding test can pin it, and offline tests never touch the live vector store.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from jarvis.redact import redact


@dataclass(frozen=True)
class Context:
    block: str  # the exact text the LLM may see
    source_ids: frozenset[str]  # ids an insight may ground itself on (memory ids + "signals")


def build_context(signals_since, memories, goals, *, now: datetime) -> Context:
    lines = [
        f"REFLECTION CONTEXT as of {now:%Y-%m-%d %H:%M}. Derive insights ONLY from this data.",
        "",
        "Recent activity (behavioral signals, no content - aggregate patterns only):",
    ]
    if signals_since:
        kinds = Counter(s.kind for s in signals_since)
        modality = Counter((s.payload or {}).get("source", "?") for s in signals_since)
        hours = Counter(s.ts.hour for s in signals_since)
        lines.append(f"  total: {len(signals_since)} signals")
        lines.append("  by kind: " + ", ".join(f"{k}={n}" for k, n in sorted(kinds.items())))
        lines.append("  by modality: " + ", ".join(f"{k}={n}" for k, n in sorted(modality.items())))
        lines.append("  by hour: " + ", ".join(f"{h:02d}h={n}" for h, n in sorted(hours.items())))
    else:
        lines.append("  (none)")

    lines += ["", "Explicit memories (the user's own stated content):"]
    lines += [f"  [{m.id}] {m.content}" for m in memories] if memories else ["  (none)"]

    lines += ["", "Active goals:"]
    lines += [f"  - {g.description}" for g in goals] if goals else ["  (none)"]

    block = redact("\n".join(lines))
    source_ids = frozenset({m.id for m in memories} | {"signals"})
    return Context(block=block, source_ids=source_ids)
