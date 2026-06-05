"""Plain CLI for Jarvis — a thin front-end over JarvisService.

The CLI only parses input and renders results; all capability logic + signal capture live in
`JarvisService`, the same facade the GUI and voice loop call. Free-text questions go through
`ask` (knowledge pipeline -> grounded cited answer, else labeled plain chat). Lines starting with
``:`` are commands: memory (:note/:notes/:recall), goals (:goal/:goals), calendar (:cal), finance
(:spend/:accounts/:budget/:categorize/:recat), the briefing (:brief), and the :signals inspector.
"""

from __future__ import annotations

from jarvis.cache.sqlite_cache import SQLiteCache
from jarvis.config import config
from jarvis.connectors.arxiv import ArxivConnector
from jarvis.connectors.caching import CachingConnector
from jarvis.connectors.fundamentals import FundamentalsConnector
from jarvis.connectors.gdelt import GdeltConnector
from jarvis.connectors.hn import HackerNewsConnector
from jarvis.connectors.markets import MarketsConnector
from jarvis.connectors.news import NewsConnector
from jarvis.finance.money import format_money
from jarvis.knowledge.answerer import Answerer
from jarvis.knowledge.pipeline import Knowledge
from jarvis.knowledge.router import Router
from jarvis.llm.client import LLMClient, OllamaClient
from jarvis.llm.embedder import OllamaEmbedder
from jarvis.memory.migrate import migrate_notes
from jarvis.memory.store import MemoryStore
from jarvis.orchestrator import Orchestrator
from jarvis.redact import redact
from jarvis.results import AgendaResult, AskResult
from jarvis.router.model_router import ModelRouter
from jarvis.service import JarvisService
from jarvis.signals.log import SignalLog
from jarvis.stores.chroma_store import ChromaVectorStore
from jarvis.stores.sqlite_store import SQLiteStructuredStore

BANNER = (
    "Jarvis (Phase 4). Ask about markets, AI/business news, or HN/YC and answers come from live\n"
    "sources with citations. General questions fall back to plain chat.\n"
    "Commands:  :note <text>  |  :notes  |  :recall <query>\n"
    "           :goal add <text>  |  :goals  |  :goal done <id>\n"
    "           :spend <q>  |  :accounts  |  :budget  |  :categorize  |  :recat <m> <cat>\n"
    "           :company <symbol|name>  |  :research <goal_id>\n"
    "           :cal  |  :brief  |  :signals  |  exit"
)


def _build_knowledge(llm: LLMClient) -> tuple[Knowledge, dict]:
    cache = SQLiteCache(config.db_path.parent / "cache.db")
    connectors = [
        CachingConnector(HackerNewsConnector(), cache, config.cache_ttl_hn),
        CachingConnector(MarketsConnector(), cache, config.cache_ttl_markets),
        CachingConnector(NewsConnector(), cache, config.cache_ttl_news),
        CachingConnector(GdeltConnector(), cache, config.cache_ttl_gdelt),
        CachingConnector(FundamentalsConnector(), cache, config.cache_ttl_fundamentals),
        CachingConnector(ArxivConnector(), cache, config.cache_ttl_arxiv),
    ]
    router = Router(llm, connectors)
    answerer = Answerer(llm)
    by_name = {c.name: c for c in connectors}
    # Same connectors power both knowledge Q&A and proactivity collector candidates (public terms).
    return Knowledge(router, by_name, answerer), by_name


def build_service(source: str) -> tuple[JarvisService, SQLiteStructuredStore]:
    """Compose the core and return a JarvisService (+ the store, for lifecycle). Shared by all
    front-ends: the CLI, the GUI (`source="gui"`), and the voice loop (`source="voice"`)."""
    config.ensure_dirs()
    llm = OllamaClient()
    knowledge, connectors = _build_knowledge(llm)
    store = SQLiteStructuredStore(config.db_path)
    # Cosine collection for the §7.1 retrieval; the memory store owns embedding + ranking.
    vector = ChromaVectorStore(config.vector_dir, collection="memory", space="cosine")
    memory = MemoryStore(vector, OllamaEmbedder())
    moved = migrate_notes(store, memory)  # one-shot Phase 0 -> Phase 2; no-op once drained
    if moved:
        print(f"(migrated {moved} legacy note(s) into memory)")
    service = JarvisService(
        orchestrator=Orchestrator(llm),
        knowledge=knowledge,
        store=store,
        memory=memory,
        signals=SignalLog(store),
        source=source,
        llm=llm,  # raw LLM for finance parse/classify (structured); phrasing uses the orchestrator
        connectors=connectors,  # collector candidates fetch public watch terms through these
        model_router=ModelRouter(),  # Tier-2 cloud seam; disabled gracefully when no key is set
    )
    return service, store


def run() -> None:
    service, store = build_service(source="cli")
    print(BANNER)
    try:
        _loop(service)
    finally:
        store.close()
    print("bye.")


def _loop(service: JarvisService) -> None:
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not text:
            continue
        if text.lower() in {"exit", "quit"}:
            return
        # One guard keeps the REPL alive if a backend call fails (the facade still logs the signal).
        try:
            if text.startswith(":"):
                _handle_command(text, service)
            else:
                _render_ask(service.ask(text))
        except Exception as exc:
            print(f"[error] {redact(str(exc))}")


def _render_ask(result: AskResult) -> None:
    if not result.grounded:  # labeled plain chat (clearly the model's own knowledge)
        print(f"jarvis (chat)> {result.text}")
        return
    marker = " (cached)" if result.cached else ""
    print(f"jarvis{marker}> {result.text}")


def _render_agenda(result: AgendaResult) -> None:
    if not result.connected:
        print("calendar not connected. Run:  python -m jarvis calendar-auth")
        return
    if not result.events:
        print("(no events today)")
        return
    for event in result.events:
        when = "all day" if event.all_day else f"{event.start:%H:%M}-{event.end:%H:%M}"
        location = f"  @ {event.location}" if event.location else ""
        print(f"  {when}  {event.summary}{location}")


def _handle_goal(argument: str, service: JarvisService) -> None:
    sub, _, rest = argument.partition(" ")
    sub, rest = sub.lower(), rest.strip()
    if sub == "add":
        if not rest:
            print("usage: :goal add <text>")
            return
        print(f"added goal #{service.add_goal(rest).id}")
    elif sub == "done":
        if not rest.isdigit():
            print("usage: :goal done <id>")
            return
        print(f"goal #{service.complete_goal(int(rest)).id} done")
    else:
        print("usage: :goal add <text> | :goal done <id>")


def _handle_budget(argument: str, service: JarvisService) -> None:
    sub, _, rest = argument.partition(" ")
    if sub.lower() == "set":
        category, _, amount = rest.strip().rpartition(" ")
        if not category or not amount:
            print("usage: :budget set <category> <amount>")
            return
        from decimal import Decimal, InvalidOperation

        try:
            budget = service.set_budget(category.strip(), Decimal(amount.strip()))
        except InvalidOperation:
            print("usage: :budget set <category> <amount>  (amount must be a number)")
            return
        except ValueError as exc:
            print(str(exc))
            return
        print(f"budget set: {budget.category} = {format_money(budget.limit)}/{budget.period}")
        return
    statuses = service.budget_status()
    if not statuses:
        print("(no budgets; :budget set <category> <amount>)")
        return
    for s in statuses:
        flag = "  OVER" if s.over else ""
        actual, limit, left = (
            format_money(s.actual),
            format_money(s.limit),
            format_money(s.remaining),
        )
        print(f"  {s.category}: {actual} of {limit} ({left} left){flag}")


def _handle_watch(argument: str, service: JarvisService) -> None:
    parts = argument.split(maxsplit=2)
    verb = parts[0].lower() if parts else "list"
    if verb == "list" or not parts:
        items = service.watchlist()
        if not items:
            print('(watchlist empty; :watch add symbol NVDA  /  :watch add topic "local LLMs")')
            return
        for w in items:
            print(f"  {w.kind}: {w.value}")
        return
    if verb in ("add", "rm", "remove") and len(parts) == 3:
        kind, value = parts[1].lower(), parts[2].strip().strip('"').strip("'")
        try:
            if verb == "add":
                watched = service.add_watch(kind, value)
                print(f"watching {watched.kind}: {watched.value}")
            else:
                service.remove_watch(kind, value)
                print(f"unwatched {kind}: {value}")
        except ValueError as exc:
            print(str(exc))
        return
    print(
        "usage: :watch list | :watch add <symbol|topic> <value> | :watch rm <symbol|topic> <value>"
    )


def _render_profile(model) -> None:
    print(f"user model (updated {model.updated_at or 'never'}):")
    print("  interests:")
    for i in model.interests:
        print(f"    - {i.topic}  (weight {i.weight:.2f}, confidence {i.confidence:.2f})")
    if not model.interests:
        print("    (none)")
    print("  rhythms:")
    for r in model.rhythms:
        print(f"    - {r.pattern}  (confidence {r.confidence:.2f})")
    if not model.rhythms:
        print("    (none)")
    print("  active goals:")
    for g in model.goals:
        print(f"    - {g.description}")
    if not model.goals:
        print("    (none)")


def _render_company(view) -> None:
    if view.note and not view.name:
        print(f"  {view.note}")
        return
    header = view.name or view.symbol
    bits = [b for b in (view.industry, view.exchange, view.market_cap) if b]
    print(f"{header} ({view.symbol})" + (f"  -  {', '.join(bits)}" if bits else ""))
    if view.metrics:
        m = view.metrics

        def show(label, key, suffix=""):
            value = m.get(key)
            if value is not None:
                print(f"    {label}: {value}{suffix}")

        show("P/E (TTM)", "pe_ttm")
        show("net margin", "net_margin_ttm", "%")
        show("gross margin", "gross_margin_ttm", "%")
        show("revenue/share", "revenue_per_share_ttm")
        show("revenue growth", "revenue_growth_yoy", "% YoY")
        if m.get("week52_low") is not None and m.get("week52_high") is not None:
            print(f"    52-week: {m['week52_low']} - {m['week52_high']}")
    if view.recommendation:
        print(f"  analysts: {view.recommendation}")
    if view.news:
        print("  recent news:")
        for article in view.news:
            print(f"    - {article.title} ({article.source})")


def _handle_command(text: str, service: JarvisService) -> None:
    command, _, argument = text[1:].partition(" ")
    command = command.lower()
    argument = argument.strip()
    if command == "note":
        if not argument:
            print("usage: :note <text>")
            return
        service.remember(argument)
        print("saved to memory")
    elif command == "notes":
        records = service.memories()
        if not records:
            print("(no memories yet)")
            return
        for record in records:
            print(f"  {record.content}")
    elif command == "recall":
        if not argument:
            print("usage: :recall <query>")
            return
        results = service.recall(argument)
        if not results:
            print("(no matches)")
            return
        for record in results:
            print(f"  {record.content}")
    elif command == "goal":
        _handle_goal(argument, service)
    elif command == "goals":
        goals = service.list_goals()
        if not goals:
            print("(no goals yet)")
            return
        for goal in goals:
            mark = "x" if goal.status == "done" else " "
            print(f"  [{mark}] #{goal.id}  {goal.description}")
    elif command in ("cal", "agenda"):
        _render_agenda(service.agenda())
    elif command in ("brief", "briefing"):
        print(service.briefing())
    elif command == "recat":
        merchant, _, category = argument.rpartition(" ")
        merchant, category = merchant.strip(), category.strip()
        if not merchant or not category:
            print("usage: :recat <merchant> <category>")
            return
        count = service.recategorize(merchant, category)
        print(f"recategorized {count} transaction(s) for '{merchant}' -> {category}")
    elif command == "spend":
        if not argument:
            print("usage: :spend <question>  (e.g. how much did I spend on dining this month)")
            return
        print(f"jarvis> {service.finance_answer(argument)}")
    elif command == "categorize":
        print(f"categorized {service.categorize_unknowns()} transaction(s)")
    elif command == "accounts":
        accounts = service.accounts()
        if not accounts:
            print("(no accounts; import an OFX/QFX file)")
            return
        for account in accounts:
            print(f"  {account.name} ({account.type}): {format_money(account.balance)}")
    elif command == "budget":
        _handle_budget(argument, service)
    elif command == "watch":
        _handle_watch(argument, service)
    elif command == "company":
        if not argument:
            print("usage: :company <symbol|name>  (e.g. :company AAPL  /  :company apple)")
            return
        _render_company(service.company(argument))
    elif command == "deepdive":
        if not argument:
            print("usage: :deepdive <symbol|name>  (cloud escalation; needs ANTHROPIC_API_KEY)")
            return
        result = service.company_deepdive(argument)
        print(result["report"] if result["report"] else result["note"])
    elif command == "research":
        if not argument.isdigit():
            print("usage: :research <goal_id>  (cloud research brief; needs ANTHROPIC_API_KEY)")
            return
        result = service.project_deepdive(int(argument))
        print(result["report"] if result["report"] else result["note"])
    elif command == "suggest":
        suggestions = service.suggestions()
        if not suggestions:
            print("(nothing worth surfacing right now)")
        for s in suggestions:
            print(f"  - {s.content}")
            print(f"    why: {s.why}")
    elif command == "rate":
        sid, _, result = argument.partition(" ")
        if not sid.strip() or not result.strip():
            print("usage: :rate <id> <acted|dismissed|ignored|more_like_this|less_like_this>")
            return
        try:
            service.record_outcome(sid.strip(), result.strip())
            print(f"recorded: {result.strip()}")
        except ValueError as exc:
            print(str(exc))
    elif command == "value":
        report = service.value_report()
        pct = f"{report['helpful_rate'] * 100:.0f}%"
        print(f"usefulness: {pct} helpful across {report['outcomes']} rated suggestion(s)")
    elif command == "reflect":
        print(f"reflected: {service.reflect(force=True)} insight(s)")
    elif command == "profile":
        if argument.lower() == "reset":
            service.reset_user_model()
            print("user model reset")
            return
        verb, _, topic = argument.partition(" ")
        if verb.lower() == "suppress":
            topic = topic.strip()
            if not topic:
                print("usage: :profile suppress <topic>")
                return
            service.suppress_topic(topic)
            print(f"suppressed: {topic} (weight + confidence decayed)")
            return
        _render_profile(service.user_model())
    elif command == "why":
        reflections = [m for m in service.memories() if m.type == "reflection"]
        if not reflections:
            print("(no inferred insights yet; run :reflect)")
            return
        for m in reflections:
            print(f"  [{m.id}] {m.content}  (from: {', '.join(m.links) or '?'})")
    elif command == "forget":
        if not argument:
            print("usage: :forget <memory-id>")
            return
        service.forget(argument)
        print(f"forgotten: {argument}")
    elif command == "signals":
        events = service.recent_signals(limit=20)
        if not events:
            print("(no signals yet)")
            return
        for event in events:
            print(f"  {event.ts:%H:%M:%S}  {event.kind}  {event.payload}")
    else:
        print(f"unknown command: :{command}")
