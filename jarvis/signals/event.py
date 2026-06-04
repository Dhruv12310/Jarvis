"""SignalEvent: the structured record emitted for every interaction (Core spec §5.4).

Dumb, cheap, append-only. Nothing learns from these in Phase 2 - the point is to accumulate history
now so the Phase 5 proactivity engine has data to learn from later.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SignalEvent:
    id: str  # uuid
    ts: datetime
    kind: str  # "query" | "command" | "briefing" | "goal_added" | "calendar_read" | ...
    payload: dict  # topic(s), path/connector, outcome, etc.
    session_id: str  # uuid per CLI session
    seq: int | None = None  # the append-only log position; None until read back from the store
