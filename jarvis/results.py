"""Structured results returned by JarvisService.

Capability methods return data, not printed strings, so every front-end (CLI, GUI, voice) renders
the same facts its own way. Goals/memories return the existing `Goal`/`MemoryRecord` value objects;
the briefing returns plain text; these two wrap the cases that need an extra flag.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AskResult:
    text: str
    grounded: bool  # True = knowledge pipeline (cited); False = labeled plain chat
    cached: bool


@dataclass(frozen=True)
class AgendaResult:
    events: list  # list[CalendarEvent]; empty when not connected or genuinely no events
    connected: bool  # False = calendar not authorized yet (front-end can prompt calendar-auth)
