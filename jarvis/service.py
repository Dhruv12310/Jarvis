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
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from jarvis.briefing import BriefingData, phrase
from jarvis.config import config
from jarvis.finance import engine, qa
from jarvis.finance.categorize import CATEGORIES, Categorizer
from jarvis.finance.money import format_money
from jarvis.finance.transaction import Account, Budget, BudgetStatus
from jarvis.knowledge.pipeline import Knowledge
from jarvis.memory.record import MemoryRecord
from jarvis.memory.store import MemoryStore
from jarvis.orchestrator import Orchestrator
from jarvis.proactivity import feedback, suggest
from jarvis.proactivity import user_model as um
from jarvis.proactivity.candidate import EngineState, Fetched
from jarvis.proactivity.generators import collector_queries
from jarvis.proactivity.reflect import reflect as _reflect
from jarvis.proactivity.trigger import accumulated_fuel, should_reflect
from jarvis.proactivity.user_model import UserModel
from jarvis.results import AgendaResult, AskResult
from jarvis.signals.event import SignalEvent
from jarvis.signals.log import SignalLog
from jarvis.stores.structured import Goal, Outcome, StructuredStore, Suggestion, Watch

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
        connectors=None,
    ) -> None:
        self._orchestrator = orchestrator
        self._knowledge = knowledge
        self._store = store
        self._memory = memory
        self._signals = signals
        self._source = source
        # raw LLM for finance's structured parse/classify; prose phrasing uses the orchestrator.
        self._llm = llm
        # public collectors for proactivity candidate fetch (queried with watchlist terms only).
        self._connectors = connectors or {}

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
            # Keep the signal log's category label an enum, not free text.
            if category not in CATEGORIES:
                raise ValueError(f"unknown category '{category}'; one of: {', '.join(CATEGORIES)}")
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

    # --- proactivity (Phase 5a): reflection. Deterministic trigger; LLM synthesizes, grounded. ---

    def reflect(self, *, force: bool = False) -> int:
        """Run reflection if the §7.4 trigger fires (or forced): grounded LLM synthesis over the
        signal history + memories + goals -> reflection memories. Returns the insights written."""
        with self._signal("reflect") as sig:
            state = self._store.get_reflection_state()
            new_signals = self._store.get_signals_since(state.last_seq)
            if not force and not should_reflect(
                accumulated_fuel(new_signals), config.reflection_threshold
            ):
                sig["reflected"] = False
                return 0
            now = datetime.now(UTC)
            goals = self._store.get_goals(status="active")
            try:
                insights = _reflect(
                    signals_since=new_signals,
                    memories=self._memory.all(),
                    goals=goals,
                    llm=self._llm,
                    memory_store=self._memory,
                    now=now,
                )
            except Exception as exc:
                # A hard synthesis failure must NOT advance the baseline: leave the window so the
                # next run retries it rather than forfeiting those signals.
                sig["reflected"] = False
                sig["error"] = type(exc).__name__
                return 0
            # Materialize the user model from insights (deterministic; frequency never amplifies).
            model = um.from_dict(self._store.get_user_model())
            for insight in insights:
                model = um.merge(
                    model,
                    insight,
                    goals,
                    now=now,
                    alpha=config.confidence_alpha,
                    gamma=config.confidence_gamma,
                )
            self._store.save_user_model(um.to_dict(model))
            # Advance the baseline to the max seq of the window we ACTUALLY processed - never the
            # global max, or a signal written during synthesis (e.g. by the always-on Heartbeat or
            # another front-end) would be skipped forever. Empty forced run: leave it where it was.
            processed_seq = new_signals[-1].seq if new_signals else state.last_seq
            self._store.save_reflection_state(processed_seq, now)
            sig["reflected"] = True
            sig["insights"] = len(insights)  # metadata only - no insight content in the log
            sig["forced"] = force
            return len(insights)

    def user_model(self) -> UserModel:
        """The inspectable user model: stored derived parts (reflection) + goals read live."""
        with self._signal("user_model"):
            model = um.from_dict(self._store.get_user_model())
            return replace(model, goals=self._store.get_goals(status="active"))

    def forget(self, memory_id: str) -> None:
        """Delete a reflection (or any) memory - the user controls their own model."""
        with self._signal("forget"):
            self._memory.forget(memory_id)

    def suppress_topic(self, topic: str) -> None:
        """User correction: stop amplifying one inferred interest. Decays its weight + confidence
        in place (a targeted pull-down, vs reset's full wipe). The topic stays out of the signal
        log (free text) - only that a suppression happened is recorded."""
        with self._signal("suppress_topic"):
            model = um.from_dict(self._store.get_user_model())
            model = um.suppress_interest(
                model, topic, now=datetime.now(UTC), gamma=config.confidence_gamma
            )
            self._store.save_user_model(um.to_dict(model))

    def reset_user_model(self) -> None:
        """Wipe the materialized user model (a user-controlled reset)."""
        with self._signal("user_model_reset"):
            self._store.clear_user_model()

    # --- watchlist (Phase 5b): the user's PUBLIC watch terms for collector candidates -------

    def add_watch(self, kind: str, value: str) -> Watch:
        """Watch a public symbol or topic. Symbols are upper-cased; this is the only data a
        collector query may be built from (the trust boundary for candidate fetch)."""
        with self._signal("watch_add") as sig:
            if kind not in ("symbol", "topic"):
                raise ValueError("watch kind must be 'symbol' or 'topic'")
            value = value.strip().upper() if kind == "symbol" else value.strip()
            self._store.add_watch(kind, value)
            sig["kind"] = kind  # kind only - the term is public but stays out of the signal log
            return Watch(kind=kind, value=value)

    def watchlist(self) -> list[Watch]:
        with self._signal("watch_list") as sig:
            items = self._store.get_watchlist()
            sig["count"] = len(items)
            return items

    def remove_watch(self, kind: str, value: str) -> None:
        with self._signal("watch_remove"):
            value = value.strip().upper() if kind == "symbol" else value.strip()
            self._store.remove_watch(kind, value)

    # --- proactivity engine (Phase 5b): generate -> rank -> phrase -> the feed ----------------

    def suggestions(self, *, now: datetime | None = None) -> list[Suggestion]:
        """Run the engine once: gather state, generate candidates, rank + gate, phrase survivors.
        Persists each surfaced Suggestion (so 5c can attach an Outcome); signals are metadata-only.
        Returns the top-K cards, or an empty list when nothing clears the bar (the common case).
        `now` is injectable for deterministic tests; production passes the real local time."""
        with self._signal("suggest") as sig:
            now = now or datetime.now().astimezone()
            built = suggest.build(self._engine_state(now), chat=self._orchestrator.chat, now=now)
            for s in built:
                self._store.save_suggestion(s)
                # attention marker for 5c - metadata only (type enum, never card text), 0 fuel.
                self._signals.emit(
                    "suggestion_shown", {"source": self._source, "type": s.candidate_type}
                )
            sig["surfaced"] = len(built)
            return built

    def _engine_state(self, now: datetime) -> EngineState:
        """Gather the deterministic snapshot the engine ranks over. The only outbound calls are
        collector fetches, and they use PUBLIC watchlist terms only (the trust boundary)."""
        today = now.date()
        month = self._store.get_transactions(start=today.replace(day=1), end=today)
        events, _connected = self._calendar_events(now)
        watch = self._store.get_watchlist()
        symbols = [w.value for w in watch if w.kind == "symbol"] or list(config.market_watchlist)
        topics = [w.value for w in watch if w.kind == "topic"]
        items = [
            Fetched(source=name, term=term, item=item)
            for name, term in collector_queries(symbols, topics)
            for item in self._fetch(name, term)
        ]
        lookback = max(config.suggestion_window_hours, config.entity_cooldown_hours)
        active_goals = self._store.get_goals(status="active")
        return EngineState(
            now=now,
            goals=active_goals,
            budget_status=engine.budget_vs_actual(month, self._store.get_budgets()),
            transactions=self._store.get_transactions(),
            events=events,
            connector_items=items,
            user_model=replace(um.from_dict(self._store.get_user_model()), goals=active_goals),
            recent_suggestions=self._store.get_recent_suggestions(
                since=now - timedelta(hours=lookback)
            ),
            feedback_weights=self._store.get_feedback_weights(),
            category_outcomes=self._store.get_category_outcomes(),
        )

    def record_outcome(self, suggestion_id: str, result: str) -> Outcome:
        """Record the user's reaction to a surfaced suggestion and fold it into learning (§7.5):
        a positive value amplifies the suggestion's GOAL-LINKED topic and the features that drove
        it; a negative one suppresses them. §8 holds (a pure-frequency topic can't be amplified,
        attention is never positive). The signal carries the result enum only, never the content."""
        with self._signal("outcome") as sig:
            if result not in feedback.RESULTS:
                raise ValueError(
                    f"unknown outcome '{result}'; one of {', '.join(feedback.RESULTS)}"
                )
            now = datetime.now(UTC)
            outcome = Outcome(suggestion_id=suggestion_id, ts=now, result=result)
            self._store.save_outcome(outcome)
            sig["result"] = result
            suggestion = self._store.get_suggestion(suggestion_id)
            if suggestion is not None:
                model = um.from_dict(self._store.get_user_model())
                model, weights = feedback.apply_outcome(
                    outcome,
                    suggestion,
                    model,
                    self._store.get_feedback_weights(),
                    self._store.get_goals(status="active"),
                    now=now,
                    alpha=config.confidence_alpha,
                    gamma=config.confidence_gamma,
                    lr=config.feedback_lr,
                )
                self._store.save_user_model(um.to_dict(model))
                self._store.save_feedback_weights(weights)
            return outcome

    def value_report(self) -> dict:
        """The holdout usefulness metric (§7.5 monitor): is Jarvis actually helping? Read-only -
        this number is never optimized against, so a gap vs the learned weights flags drift."""
        outcomes = self._store.get_category_outcomes()
        return {"helpful_rate": feedback.value_metric(outcomes), "outcomes": len(outcomes)}

    def _fetch(self, name: str, term: str) -> list:
        """Fetch a connector's items for a public term; a missing/failing source is empty."""
        connector = self._connectors.get(name)
        if connector is None:
            return []
        try:
            return connector.fetch(term).items
        except Exception:
            return []

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
                return (
                    f"Spent {format_money(total)} so far this month; "
                    f"top category: {top} ({format_money(amount)})."
                )
            return f"Spent {format_money(total)} so far this month."
        except Exception:
            return None
