"""SignalLog: emit one SignalEvent per interaction via the structured store.

Capture must never break or slow an interaction, so ``emit`` swallows any error. One session id is
generated per ``SignalLog`` (i.e. per CLI session).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from jarvis.signals.event import SignalEvent
from jarvis.stores.structured import StructuredStore


class SignalLog:
    def __init__(self, store: StructuredStore, session_id: str | None = None) -> None:
        self._store = store
        self._session_id = session_id or str(uuid4())

    def emit(self, kind: str, payload: dict | None = None) -> None:
        try:
            self._store.save_signal(
                SignalEvent(
                    id=str(uuid4()),
                    ts=datetime.now(UTC),
                    kind=kind,
                    payload=payload or {},
                    session_id=self._session_id,
                )
            )
        except Exception:  # capture is best-effort; it must never break an interaction
            pass
