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
from jarvis.connectors.caching import CachingConnector
from jarvis.connectors.hn import HackerNewsConnector
from jarvis.connectors.markets import MarketsConnector
from jarvis.connectors.news import NewsConnector
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
    "           :cal  |  :brief  |  :signals  |  exit"
)


def _build_knowledge(llm: LLMClient) -> Knowledge:
    cache = SQLiteCache(config.db_path.parent / "cache.db")
    connectors = [
        CachingConnector(HackerNewsConnector(), cache, config.cache_ttl_hn),
        CachingConnector(MarketsConnector(), cache, config.cache_ttl_markets),
        CachingConnector(NewsConnector(), cache, config.cache_ttl_news),
    ]
    router = Router(llm, connectors)
    answerer = Answerer(llm)
    return Knowledge(router, {c.name: c for c in connectors}, answerer)


def build_service(source: str) -> tuple[JarvisService, SQLiteStructuredStore]:
    """Compose the core and return a JarvisService (+ the store, for lifecycle). Shared by all
    front-ends: the CLI, the GUI (`source="gui"`), and the voice loop (`source="voice"`)."""
    config.ensure_dirs()
    llm = OllamaClient()
    knowledge = _build_knowledge(llm)
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
        print(f"budget set: {budget.category} = {budget.limit}/{budget.period}")
        return
    statuses = service.budget_status()
    if not statuses:
        print("(no budgets; :budget set <category> <amount>)")
        return
    for s in statuses:
        flag = "  OVER" if s.over else ""
        print(f"  {s.category}: {s.actual} of {s.limit} ({s.remaining} left){flag}")


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
            print(f"  {account.name} ({account.type}): {account.balance}")
    elif command == "budget":
        _handle_budget(argument, service)
    elif command == "signals":
        events = service.recent_signals(limit=20)
        if not events:
            print("(no signals yet)")
            return
        for event in events:
            print(f"  {event.ts:%H:%M:%S}  {event.kind}  {event.payload}")
    else:
        print(f"unknown command: :{command}")
