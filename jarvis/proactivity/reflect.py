"""Reflection synthesis (Stage 4): the LLM proposes typed insights over the grounded context; code
validates them and writes the survivors as `reflection` memories.

Grounding is enforced, not assumed: an insight is kept only if it is well-typed, links to source ids
that resolve to the assembled context, and does not reproduce a source memory verbatim (it must
abstract). Malformed/ungrounded items are dropped, never crash. The LLM is injected (a `generate`
callable), so this module imports no model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from jarvis.memory.record import MemoryRecord
from jarvis.proactivity.context import Context, build_context

_KINDS = ("interest", "rhythm", "preference", "observation")

_SCHEMA = {
    "type": "object",
    "properties": {
        "insights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": list(_KINDS)},
                    "content": {"type": "string"},
                    "topic": {"type": ["string", "null"]},
                    "weight": {"type": ["number", "null"]},
                    "links": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["kind", "content", "links"],
            },
        }
    },
    "required": ["insights"],
}

_PROMPT = (
    "You are reflecting on a user to surface higher-level insights. Use ONLY the data in the "
    "context below; do not invent anything not supported by it. For each insight, set `links` to "
    "the source ids it derives from (a memory id shown in brackets, or 'signals' for a behavioral "
    "pattern). Each insight must be an abstraction, not a copy of a line.\n\nCONTEXT:\n{block}"
)


@dataclass(frozen=True)
class Insight:
    kind: str  # interest | rhythm | preference | observation
    content: str
    links: list[str]
    topic: str | None = None
    weight: float | None = None
    metadata: dict = field(default_factory=dict)


def synthesize(context: Context, llm) -> list[Insight]:
    """Ask the LLM for typed insights, then keep only the well-typed + grounded ones.

    A hard failure (the LLM call raises, or the response is unparseable) PROPAGATES so the caller
    can leave the reflection baseline un-advanced and retry the window - a transient model outage
    must not silently consume a day of signals. A clean parse with zero survivors returns []."""
    data = json.loads(
        llm.generate(_PROMPT.format(block=context.block), format=_SCHEMA, think=False)
    )
    insights = []
    for item in data.get("insights", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        kind, content, links = item.get("kind"), item.get("content"), item.get("links")
        if kind not in _KINDS or not isinstance(content, str) or not content.strip():
            continue  # malformed -> drop
        if not links or not all(link in context.source_ids for link in links):
            continue  # ungrounded -> drop (links must resolve to the context)
        insights.append(
            Insight(kind=kind, content=content.strip(), links=list(links), topic=item.get("topic"))
        )
    return insights


def reflect(*, signals_since, memories, goals, llm, memory_store, now: datetime) -> list[Insight]:
    """Build the grounded context, synthesize, drop verbatim reuse, write reflection memories."""
    context = build_context(signals_since, memories, goals, now=now)
    memory_texts = {m.content.strip().lower() for m in memories}
    written = []
    for insight in synthesize(context, llm):
        if insight.content.strip().lower() in memory_texts:
            continue  # reflection must abstract, never restate a memory verbatim
        memory_store.save(_to_reflection_record(insight, now))
        written.append(insight)
    return written


def _to_reflection_record(insight: Insight, now: datetime) -> MemoryRecord:
    return MemoryRecord(
        id=uuid4().hex,
        type="reflection",
        content=insight.content,
        created_at=now,
        last_accessed_at=now,
        importance=0.6,
        tier="tactical",
        confidence=0.6,
        source="reflection",
        links=insight.links,
        metadata={"insight_kind": insight.kind, "topic": insight.topic},
    )
