"""Daily briefing: deterministically assemble the day's data, then let the LLM only phrase it.

Deterministic-first (Core invariant): the calendar events, active goals, and knowledge digest are
gathered and laid out by code into a DATA block. The LLM receives ONLY that block and turns it into
prose - it never sources facts itself. Inputs are duck-typed (events expose summary/start/end/
location/all_day; goals expose description) so this module stays decoupled from calendar/store.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BriefingData:
    when: datetime
    events: list  # CalendarEvent-like
    goals: list  # Goal-like
    digest: str | None  # Phase-1 knowledge digest text, or None
    finance: str | None = None  # deterministic finance line (engine-computed), or None


_PROMPT = (
    "Assemble a short morning briefing from the DATA below. Use ONLY this data; do not invent "
    "events, goals, or facts. If a section is empty, note it briefly. Preserve any source "
    "citations present in the digest. Keep it concise and friendly.\n\nDATA:\n{block}"
)


def to_data_block(data: BriefingData) -> str:
    """Render the gathered data into the exact text the LLM is allowed to see."""
    lines = [f"Date: {data.when:%A, %B %d, %Y}", "", "Calendar:"]
    if data.events:
        for event in data.events:
            when = "all day" if event.all_day else f"{event.start:%H:%M}-{event.end:%H:%M}"
            location = f" @ {event.location}" if event.location else ""
            lines.append(f"  - {when} {event.summary}{location}")
    else:
        lines.append("  (no events today)")
    lines += ["", "Active goals:"]
    if data.goals:
        lines += [f"  - {goal.description}" for goal in data.goals]
    else:
        lines.append("  (none)")
    if data.finance is not None:
        lines += ["", "Finance:", f"  {data.finance}"]
    lines += ["", "Knowledge digest:", f"  {data.digest}" if data.digest else "  (none)"]
    return "\n".join(lines)


def phrase(data: BriefingData, generate: Callable[[str], str]) -> str:
    """Phrase the briefing. ``generate`` is any prompt->text callable (e.g. orchestrator.chat)."""
    return generate(_PROMPT.format(block=to_data_block(data)))
