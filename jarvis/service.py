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
from datetime import date, datetime

from jarvis.briefing import BriefingData, phrase
from jarvis.finance import engine, qa
from jarvis.finance.categorize import Categorizer
from jarvis.finance.transaction import Account, Budget, BudgetStatus
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
        llm=None,
    ) -> None:
        self._orchestrator = orchestrator
        self._knowledge = knowledge
        self._store = store
        self._memory = memory
        self._signals = signals
        self._source = source
        # raw LLM for finance's structured parse/classify; prose phrasing uses the orchestrator.
        self._llm = llm

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
                finance=self._brief_finance(),
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

    # --- finance (every figure from the engine; the LLM only parses + phrases) --------------

    def finance_answer(self, question: str) -> str:
        """Answer a finance question: LLM parses -> engine computes the figure -> LLM phrases it."""
        with self._signal("finance_query") as sig:
            query = qa.parse_question(question, self._llm)
            value, label = qa.compute(
                query, self._store.get_transactions(), self._store.get_accounts(), date.today()
            )
            sig["metric"] = query.metric  # no amount in the signal log
            return self._orchestrator.chat(qa.phrase_prompt(question, label, value)).strip()

    def categorize_unknowns(self) -> int:
        """Fill 'uncategorized' transactions using the LLM (per merchant); return the count."""
        with self._signal("categorize") as sig:
            categorizer = Categorizer(overrides=self._store.get_category_overrides(), llm=self._llm)
            merchants = {t.merchant for t in self._store.get_transactions(category="uncategorized")}
            count = 0
            for merchant in merchants:
                category = categorizer.categorize(merchant)
                if category != "uncategorized":
                    count += self._store.recategorize_merchant(merchant, category)
            sig["updated"] = count
            return count

    def accounts(self) -> list[Account]:
        with self._signal("accounts") as sig:
            accounts = self._store.get_accounts()
            sig["count"] = len(accounts)
            return accounts

    def set_budget(self, category: str, limit, period: str = "monthly") -> Budget:
        with self._signal("budget_set") as sig:
            budget = Budget(category=category, limit=limit, period=period)
            self._store.save_budget(budget)
            sig["category"] = category
            return budget

    def budget_status(self) -> list[BudgetStatus]:
        """Deterministic budget-vs-actual over this month's transactions."""
        with self._signal("budget_status"):
            today = date.today()
            month = self._store.get_transactions(start=today.replace(day=1), end=today)
            return engine.budget_vs_actual(month, self._store.get_budgets())

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

    def _brief_finance(self) -> str | None:
        # Deterministic, engine-computed: month-to-date spend + top category. None when no data.
        try:
            today = date.today()
            month = self._store.get_transactions(start=today.replace(day=1), end=today)
            if not month:
                return None
            total = engine.total_spending(month)
            by_category = engine.spending_by_category(month)
            if by_category:
                top, amount = max(by_category.items(), key=lambda kv: kv[1])
                return f"Spent ${total} so far this month; top category: {top} (${amount})."
            return f"Spent ${total} so far this month."
        except Exception:
            return None
