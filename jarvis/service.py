"""JarvisService: the one application-service facade every front-end calls.

The CLI, GUI, and voice loop are thin front-ends over THIS - they call these capability methods and
render the structured results their own way; none reimplements core logic. The facade composes the
existing core (orchestrator, knowledge pipeline, store, memory, calendar, briefing) and is the one
place signal capture happens: every capability call emits exactly one SignalEvent, stamped with
`source` ("cli"|"gui"|"voice") so Phase 5's history covers all modalities. Deterministic work
stays in the engines; the LLM is only the existing routing/summarizing/briefing calls.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

from jarvis.briefing import BriefingData, phrase
from jarvis.knowledge.pipeline import Knowledge
from jarvis.memory.record import MemoryRecord
from jarvis.memory.store import MemoryStore
from jarvis.orchestrator import Orchestrator
from jarvis.results import AgendaResult, AskResult
from jarvis.signals.event import SignalEvent
from jarvis.signals.log import SignalLog
from jarvis.stores.structured import Goal, StructuredStore

# What the briefing pulls from the Phase-1 knowledge pipeline. Fixed for Phase 2/3; goal-derived
# digests are a later refinement.
_DIGEST_QUERY = "What are today's top market and tech news headlines?"


class JarvisService:
    def __init__(
        self,
        *,
        orchestrator: Orchestrator,
        knowledge: Knowledge,
        store: StructuredStore,
        memory: MemoryStore,
        signals: SignalLog,
        source: str,
    ) -> None:
        self._orchestrator = orchestrator
        self._knowledge = knowledge
        self._store = store
        self._memory = memory
        self._signals = signals
        self._source = source

    # --- capabilities (each emits exactly one signal, including on failure) -----------------

    def ask(self, text: str) -> AskResult:
        with self._signal("ask") as sig:
            answer = self._knowledge.ask(text)
            if answer is None:  # no connector -> labeled plain chat (the model's own knowledge)
                sig["path"] = "chat"
                return AskResult(
                    text=self._orchestrator.chat(text).strip(), grounded=False, cached=False
                )
            sig["path"] = "knowledge"
            sig["cached"] = answer.cached
            return AskResult(text=answer.text, grounded=True, cached=answer.cached)

    def briefing(self) -> str:
        with self._signal("briefing"):
            now = datetime.now().astimezone()
            data = BriefingData(
                when=now,
                events=self._brief_events(now),
                goals=self._store.get_goals(status="active"),
                digest=self._brief_digest(),
            )
            return phrase(data, self._orchestrator.chat)

    def add_goal(self, text: str) -> Goal:
        with self._signal("goal_add") as sig:
            goal = self._store.save_goal(text)
            sig["id"] = goal.id
            return goal

    def list_goals(self) -> list[Goal]:
        with self._signal("goal_list") as sig:
            goals = self._store.get_goals()
            sig["count"] = len(goals)
            return goals

    def complete_goal(self, goal_id: int) -> Goal:
        with self._signal("goal_done") as sig:
            sig["id"] = goal_id
            return self._store.update_goal(goal_id, status="done", progress=1.0)

    def agenda(self) -> AgendaResult:
        with self._signal("agenda") as sig:
            events, connected = self._calendar_events(datetime.now().astimezone())
            sig["connected"] = connected
            sig["count"] = len(events)
            return AgendaResult(events=events, connected=connected)

    def remember(self, text: str) -> MemoryRecord:
        with self._signal("remember"):
            return self._memory.remember(text, explicit=True)

    def memories(self) -> list[MemoryRecord]:
        with self._signal("memory_list") as sig:
            records = self._memory.all()
            sig["count"] = len(records)
            return records

    def recall(self, query: str) -> list[MemoryRecord]:
        with self._signal("recall") as sig:
            records = self._memory.retrieve(query, k=5)
            sig["count"] = len(records)
            return records

    def recategorize(self, merchant: str, category: str) -> int:
        """Persist a category correction for a merchant and apply it to stored transactions."""
        with self._signal("recategorize") as sig:
            self._store.save_category_override(merchant, category)
            count = self._store.recategorize_merchant(merchant, category)
            sig["category"] = category  # no merchant string / no amount in the signal log
            sig["updated"] = count
            return count

    def recent_signals(self, limit: int = 20) -> list[SignalEvent]:
        """Read-only inspector over the raw signal log. Does NOT emit (it would self-reference)."""
        return self._store.get_signals(limit=limit)

    # --- signal capture + best-effort briefing sources -------------------------------------

    @contextmanager
    def _signal(self, kind: str, payload: dict | None = None):
        # Emits once on the way out (success or failure), stamping source + any error type. Callers
        # mutate the yielded dict to record outcome (path, count, id, ...).
        data = {**(payload or {}), "source": self._source}
        try:
            yield data
        except Exception as exc:
            data["error"] = type(exc).__name__
            raise
        finally:
            self._signals.emit(kind, data)

    def _calendar_events(self, now: datetime) -> tuple[list, bool]:
        """(today's events, connected). A transport/auth failure degrades to ([], False) - agenda
        and briefing both treat an unreachable calendar as 'no events' rather than raising."""
        # Lazy import so the google libs only load when the calendar is actually used.
        from jarvis.calendar.client import connect, day_bounds

        try:
            client = connect()
            if client is None:
                return [], False
            return client.list_events(*day_bounds(now)), True
        except Exception:
            return [], False

    def _brief_events(self, now: datetime) -> list:
        events, _connected = self._calendar_events(now)
        return events

    def _brief_digest(self) -> str | None:
        try:
            answer = self._knowledge.ask(_DIGEST_QUERY)
            return answer.text if answer else None
        except Exception:
            return None  # digest unavailable -> empty section, briefing still renders
