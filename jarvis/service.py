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
from pathlib import Path

from jarvis import fs_ops
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
from jarvis.proactivity.goal_terms import GoalTerms, extract_terms
from jarvis.proactivity.reflect import reflect as _reflect
from jarvis.proactivity.trigger import accumulated_fuel, should_reflect
from jarvis.proactivity.user_model import UserModel
from jarvis.results import (
    AgendaResult,
    AskResult,
    CompanyNews,
    CompanyView,
    GoalFeed,
    GoalFeedItem,
    NewsItem,
    Quote,
    SymbolMatch,
)
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
        model_router=None,
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
        # Tier-2 cloud escalation seam (opt-in). None / unavailable -> Deep Dive degrades cleanly.
        self._model_router = model_router

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

    # --- live market reads (cockpit tiles): READ-ONLY inspectors, no signal --------------------

    def quotes(self, symbols: list[str] | None = None) -> list[Quote]:
        """Live market quotes for the cockpit's stock tiles (deterministic; no LLM).

        A READ-ONLY inspector like recent_signals(): it does NOT emit a SignalEvent, because the
        cockpit polls it every few seconds and a per-poll signal would flood the log and inflate
        reflection fuel. `symbols` None -> the user's watched symbol terms (the same public source
        the proactivity engine reads, so 'track any company' = add_watch + this), falling back to
        config.market_watchlist. A missing/failing markets connector yields []; an unknown ticker is
        simply absent. Never raises, never invents a price."""
        if symbols is None:
            watch = self._store.get_watchlist()
            symbols = [w.value for w in watch if w.kind == "symbol"] or list(
                config.market_watchlist
            )
        else:
            symbols = [s.strip().upper() for s in symbols if s.strip()]
        quotes: list[Quote] = []
        for symbol in symbols:
            for item in self._fetch("markets", symbol):  # one quote per requested symbol, in order
                extra = item.extra or {}
                price = float(extra.get("price") or 0.0)
                prev = float(extra.get("prev_close") or 0.0)
                quotes.append(
                    Quote(
                        symbol=item.title,
                        price=price,
                        change=price - prev,
                        change_pct=float(extra.get("change_pct") or 0.0),
                        prev_close=prev,
                    )
                )
        return quotes

    def symbol_search(self, query: str) -> list[SymbolMatch]:
        """Resolve a company name or ticker to candidate symbols so the cockpit can 'track any
        company' by name (deterministic lookup via the markets connector's Finnhub /search; no LLM).
        Read-only inspector like quotes(): does NOT emit a signal (the cockpit calls it per
        keystroke). Empty on no connector / no key / no match / failure - never invents a symbol."""
        connector = self._connectors.get("markets")
        if connector is None:
            return []
        try:
            matches = connector.search(query)
        except Exception:
            return []
        return [SymbolMatch(symbol=symbol, description=desc) for symbol, desc in matches]

    def news(self, query: str | None = None) -> list[NewsItem]:
        """World news for the News view + globe (deterministic; no LLM). A READ-ONLY inspector like
        quotes()/symbol_search(): does NOT emit a SignalEvent, because the News view polls it and a
        per-poll signal would flood the log + inflate reflection fuel. Reads the keyless GDELT
        firehose (+ GNews secondary) via self._fetch and maps each Item.extra into a NewsItem.
        `query` None -> a broad world-events net. A missing/failing source yields []; never raises,
        never invents a headline or a country."""
        term = (query or "").strip() or "world news"
        items: list[NewsItem] = []
        seen: set[str] = set()
        for name in ("gdelt", "news"):  # GDELT first (carries country); GNews adds headlines
            for item in self._fetch(name, term):
                key = item.url or item.title
                if not item.title or key in seen:
                    continue
                seen.add(key)
                extra = item.extra or {}
                seen_date = extra.get("seendate") or ""
                published = (
                    f"{seen_date[0:4]}-{seen_date[4:6]}-{seen_date[6:8]}"
                    if len(seen_date) >= 8
                    else (extra.get("published_at") or "")[:10] or None
                )
                items.append(
                    NewsItem(
                        title=item.title,
                        source=extra.get("source") or "",
                        url=item.url,
                        country=extra.get("country"),  # GNews has none -> None (no globe pin)
                        published=published,
                        image=extra.get("image"),
                    )
                )
        return items

    def company(self, query: str) -> CompanyView:
        """Deterministic company depth (market cap, financials, analyst trend, recent news) from the
        fundamentals connector. Resolves a typed NAME to a ticker via symbol_search first, then
        assembles the facets in code - the LLM is never touched here (the optional Deep Dive is a
        separate Tier-2 call). Emits one signal (symbol metadata only). No data / no key -> a
        CompanyView whose `note` explains why; never raises, never invents a figure."""
        with self._signal("company") as sig:
            view = self._company_view(query)
            sig["symbol"] = view.symbol  # symbol only - no figures in the signal log
            return view

    def _company_view(self, query: str) -> CompanyView:
        """Gather + assemble the deterministic CompanyView (NO signal - shared by company() and the
        deep dive so each emits exactly one signal of its own)."""
        symbol = self._resolve_symbol(query)
        return _assemble_company(symbol, self._fetch("fundamentals", symbol))

    def company_deepdive(self, query: str) -> dict:
        """Tier-2 cloud escalation (opt-in): an analyst-style synthesis over the SAME deterministic
        CompanyView. The Model Router is the only cloud seam and redacts before sending. Returns a
        dict {symbol, report, note, escalated}. No router/key, no data, or a cloud failure ->
        report=None with an explanatory note and escalated=False; never raises. One signal."""
        with self._signal("company_deepdive") as sig:
            view = self._company_view(query)
            sig["symbol"] = view.symbol

            def disabled(note: str, *, escalated: bool = False) -> dict:
                sig["escalated"] = escalated
                return {"symbol": view.symbol, "report": None, "note": note, "escalated": escalated}

            if self._model_router is None or not self._model_router.available:
                return disabled(
                    "Deep Dive is disabled. Set ANTHROPIC_API_KEY to enable cloud escalation."
                )
            if not view.name:  # nothing to analyze - don't spend cloud tokens on an empty view
                return disabled(view.note or "No company data to analyze.")
            try:
                report = self._model_router.deepdive(_company_block(view), _DEEPDIVE_INSTRUCTION)
            except Exception as exc:
                sig["error"] = type(exc).__name__
                return disabled("Cloud deep-dive failed; the deterministic view is unaffected.")
            sig["escalated"] = True
            return {"symbol": view.symbol, "report": report, "note": None, "escalated": True}

    def _resolve_symbol(self, query: str) -> str:
        """An already-uppercase ticker passes through; anything else (a name, or lower-case input)
        resolves via symbol_search so 'apple' -> AAPL but 'AAPL' costs no lookup. Tickers are
        uppercase by convention, which keeps a 5-letter word like 'apple' from posing as one."""
        candidate = query.strip()
        if candidate.isalpha() and candidate.isupper() and 1 <= len(candidate) <= 5:
            return candidate
        matches = self.symbol_search(query)
        return matches[0].symbol if matches else candidate.upper()

    # --- file operations (cockpit shortcut bar): deterministic pathlib, full-disk reach --------
    # The off-loopback WRITE guard is a network-bind concern and lives in the API layer; the facade
    # just honors the kill switch. No file CONTENT ever enters the signal log - only the basename +
    # byte length (metadata), never the directory chain.

    def create_file(self, path: str, content: str = "", *, overwrite: bool = False) -> dict:
        with self._signal("fs_file") as sig:
            if not config.fs_writes_enabled:
                raise ValueError("file writes are disabled")
            result = fs_ops.create_file(path, content, overwrite=overwrite)
            sig["name"] = Path(result["path"]).name  # basename only, never the dir chain
            sig["bytes"] = result["bytes"]  # length only, never the content
            sig["overwrite"] = overwrite
            return result

    def create_folder(self, path: str) -> dict:
        with self._signal("fs_folder") as sig:
            if not config.fs_writes_enabled:
                raise ValueError("file writes are disabled")
            result = fs_ops.create_folder(path)
            sig["name"] = Path(result["path"]).name
            sig["created"] = result["created"]
            return result

    def list_dir(self, path: str | None = None) -> dict:
        # A read - intentionally not behind the fs_writes_enabled kill switch (browsing stays on).
        with self._signal("fs_list") as sig:
            result = fs_ops.list_dir(path)
            sig["count"] = len(result["entries"])  # count only, never the names
            return result

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

    # --- goal-driven feed (PULL view): per active goal, deterministic relevant info + WHY --------

    def goal_feed(self) -> list[GoalFeed]:
        """User-PULLED view: for EACH active goal, deterministically derive public query terms,
        fetch related public info (markets for implied tickers, news/HN for topics), optionally a
        grounded knowledge snippet, and attach any standing Suggestion that resolves to this goal -
        each with a deterministic WHY. Unlike suggestions() (the strict PUSH ranker that abstains),
        this PULL view does NOT gate on usefulness: it is non-empty whenever a source has data.

        Deterministic-first: term extraction, ranking-by-fetch-order, and the WHY are all code; the
        LLM is touched at most for the optional grounded snippet (knowledge.ask), never for ranking.
        Trust boundary: only goal-derived PUBLIC terms (tickers/keywords) go outbound, never the raw
        goal text. Emits one signal ('goal_feed', metadata = goal + item counts, NO content). Never
        raises - per goal it degrades to [] items; the whole call degrades to [] feeds."""
        with self._signal("goal_feed") as sig:
            cap = config.goal_feed_per_goal_cap
            try:
                goals = self._store.get_goals(status="active")
            except Exception:
                sig["goals"] = 0
                sig["items"] = 0
                return []
            feeds: list[GoalFeed] = []
            total_items = 0
            for goal in goals:
                items = self._feed_for_goal(goal, cap)
                total_items += len(items)
                feeds.append(GoalFeed(goal_id=goal.id, goal=goal.description, items=items))
            sig["goals"] = len(goals)  # counts only - never a goal description or item content
            sig["items"] = total_items
            return feeds

    def _feed_for_goal(self, goal, cap: int) -> list[GoalFeedItem]:
        """Best-effort relevant items for ONE goal, capped. A sub-failure yields fewer items, not
        an exception - the whole method is wrapped so one bad goal can't sink the feed."""
        try:
            terms = extract_terms(goal.description)
            items: list[GoalFeedItem] = []
            items += self._feed_connectors(goal, terms, cap)
            if len(items) < cap:
                items += self._feed_knowledge(goal, terms, cap - len(items))
            items += self._feed_suggestions(goal)  # standing PUSH cards already tied to this goal
            return self._dedup_cap(items, cap)
        except Exception:
            return []

    def _feed_connectors(self, goal, terms: GoalTerms, cap: int) -> list[GoalFeedItem]:
        """Markets for implied tickers + news/HN for topics, via the PUBLIC (connector, term) plan.
        Reuses collector_queries() and self._fetch, like the engine (a failing source -> [])."""
        why = self._why(goal)
        kinds = {"markets": "market", "news": "news", "hn": "story"}
        out: list[GoalFeedItem] = []
        for name, term in collector_queries(terms.symbols, terms.topics):
            for item in self._fetch(name, term):  # existing helper: try/except -> [] on failure
                out.append(
                    GoalFeedItem(
                        title=item.title,
                        detail=item.detail,
                        why=f"{why} (matched '{term}')",
                        source=name,
                        kind=kinds.get(name, name),
                        url=getattr(item, "url", None),
                    )
                )
                if len(out) >= cap:  # structural cap: fetch order is the deterministic ranking
                    return out
        return out

    def _feed_knowledge(self, goal, terms: GoalTerms, budget: int) -> list[GoalFeedItem]:
        """One optional grounded snippet from the Phase-1 pipeline, built from PUBLIC terms only
        (never the raw goal text). knowledge.ask routes + may phrase via the LLM; returns None when
        no connector applies. Contained: any failure yields no snippet, not an exception."""
        if budget <= 0 or not (terms.symbols or terms.topics):
            return []
        query = self._public_query(terms)
        try:
            answer = self._knowledge.ask(query)
        except Exception:
            return []
        if answer is None or not answer.text.strip():
            return []
        return [
            GoalFeedItem(
                title=query,
                detail=answer.text.strip(),
                why=self._why(goal),
                source="knowledge",
                kind="snippet",
                url=None,
            )
        ]

    def _feed_suggestions(self, goal) -> list[GoalFeedItem]:
        """Attach any standing PUSH Suggestion that resolves to THIS goal (source_id 'goal:<id>').
        These already cleared the strict ranker, so they're high-value context for the pull view."""
        key = f"goal:{goal.id}"
        try:
            recent = self._store.get_recent_suggestions(
                since=datetime.now().astimezone() - timedelta(hours=config.suggestion_window_hours)
            )
        except Exception:
            return []
        out: list[GoalFeedItem] = []
        for s in recent:
            if key in (s.source_ids or []) or key in (s.entity_key or ""):
                out.append(
                    GoalFeedItem(
                        title=s.candidate_type,
                        detail=s.content,
                        why=s.why,  # already-deterministic provenance WHY
                        source="suggestion",
                        kind="suggestion",
                        url=None,
                    )
                )
        return out

    @staticmethod
    def _why(goal) -> str:
        """Deterministic WHY - the required provenance line, no LLM verdict."""
        return f"relates to goal #{goal.id}: {goal.description}"

    @staticmethod
    def _public_query(terms: GoalTerms) -> str:
        """A PUBLIC, goal-derived query for the knowledge pipeline (terms only, no raw goal)."""
        parts = list(terms.symbols) + list(terms.topics)
        return f"What's the latest on {', '.join(parts[:3])}?"

    @staticmethod
    def _dedup_cap(items: list[GoalFeedItem], cap: int) -> list[GoalFeedItem]:
        """De-dup by (source, url or title), preserve order, cap FETCHED items while ALWAYS keeping
        attached suggestions (owned context, not volume-capped fetches)."""
        seen: set[tuple] = set()
        fetched: list[GoalFeedItem] = []
        owned: list[GoalFeedItem] = []
        for it in items:
            sig_key = (it.source, it.url or it.title)
            if sig_key in seen:
                continue
            seen.add(sig_key)
            (owned if it.source == "suggestion" else fetched).append(it)
        return fetched[:cap] + owned

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


_DEEPDIVE_INSTRUCTION = (
    "You are an equity research analyst. Using ONLY the public company data below, write a concise "
    "deep dive: what the company does, its financial health (read from the metrics), valuation, "
    "analyst sentiment, notable recent developments (from the news), and the key risks. Do not "
    "invent any figure that is not present in the data."
)


def _company_block(view: CompanyView) -> str:
    """Render a CompanyView into the public text block the Model Router sends to the cloud. Pure;
    contains only the deterministic facts already gathered (no private data, no secrets)."""
    lines = [f"Company: {view.name or view.symbol} ({view.symbol})"]
    for label, value in (
        ("Industry", view.industry),
        ("Exchange", view.exchange),
        ("Market cap", view.market_cap),
        ("IPO", view.ipo),
    ):
        if value:
            lines.append(f"{label}: {value}")
    if view.metrics:
        lines.append("Metrics:")
        lines += [f"  {key}: {value}" for key, value in view.metrics.items() if value is not None]
    if view.recommendation:
        lines.append(f"Analyst recommendation: {view.recommendation}")
    if view.news:
        lines.append("Recent news:")
        lines += [f"  - {article.title} ({article.source})" for article in view.news]
    return "\n".join(lines)


def _assemble_company(symbol: str, items: list) -> CompanyView:
    """Fold the fundamentals connector's facet Items into a CompanyView (pure, deterministic - no
    LLM, no I/O). Each facet is optional: a missing one just leaves its field empty. No items ->
    a CompanyView with an explanatory `note` (bad ticker, or no markets API key)."""
    if not items:
        return CompanyView(
            symbol=symbol,
            note="No company data available (check the ticker, or set the markets API key).",
        )
    profile: dict = {}
    financials: dict = {}
    recommendation: str | None = None
    news: list[CompanyNews] = []
    for item in items:
        extra = item.extra or {}
        kind = extra.get("kind")
        if kind == "profile":
            profile = extra
        elif kind == "financials":
            financials = extra
        elif kind == "recommendation":
            recommendation = item.detail
        elif kind == "news":
            news.append(
                CompanyNews(title=item.title, source=extra.get("source") or "", url=item.url)
            )
    metrics = {
        k: v for k, v in financials.items() if k not in ("kind", "symbol") and v is not None
    } or None
    return CompanyView(
        symbol=symbol,
        name=profile.get("name"),
        industry=profile.get("industry"),
        exchange=profile.get("exchange"),
        market_cap=profile.get("market_cap"),
        ipo=profile.get("ipo"),
        weburl=profile.get("weburl"),
        metrics=metrics,
        recommendation=recommendation,
        news=news,
        sources=["Finnhub"],
    )
