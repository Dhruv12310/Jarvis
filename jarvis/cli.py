"""Plain CLI for Jarvis.

Free-text questions go through the knowledge pipeline (route -> deterministic fetch -> grounded,
cited summary). When no connector applies it falls back to labeled plain chat. Lines starting with
``:`` are commands: memory (:note/:notes/:recall), goals (:goal/:goals), calendar (:cal),
the daily briefing (:brief), and the :signals inspector.
"""

from __future__ import annotations

import re
from datetime import datetime

from jarvis.briefing import BriefingData, phrase
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
from jarvis.signals.log import SignalLog
from jarvis.stores.chroma_store import ChromaVectorStore
from jarvis.stores.sqlite_store import SQLiteStructuredStore
from jarvis.stores.structured import StructuredStore

BANNER = (
    "Jarvis (Phase 2). Ask about markets, AI/business news, or HN/YC and answers come from live\n"
    "sources with citations. General questions fall back to plain chat.\n"
    "Commands:  :note <text>  |  :notes  |  :recall <query>\n"
    "           :goal add <text>  |  :goals  |  :goal done <id>\n"
    "           :cal  |  :brief  |  :signals  |  exit"
)

# Redact API keys from any error text before it reaches the terminal. Defense in depth: the keyed
# connectors return empty on a non-200 rather than raising, but a future change must not leak a key.
_SECRET_PARAM = re.compile(r"(token|apikey)=[^&\s]+", re.IGNORECASE)


def _redact(text: str) -> str:
    return _SECRET_PARAM.sub(r"\1=***", text)


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


def run() -> None:
    config.ensure_dirs()
    llm = OllamaClient()
    orchestrator = Orchestrator(llm)
    knowledge = _build_knowledge(llm)
    store = SQLiteStructuredStore(config.db_path)
    # Cosine collection for the §7.1 retrieval; the memory store owns embedding + ranking.
    vector = ChromaVectorStore(config.vector_dir, collection="memory", space="cosine")
    memory = MemoryStore(vector, OllamaEmbedder())
    moved = migrate_notes(store, memory)  # one-shot Phase 0 -> Phase 2; no-op once drained
    if moved:
        print(f"(migrated {moved} legacy note(s) into memory)")
    signals = SignalLog(store)
    print(BANNER)
    try:
        _loop(orchestrator, knowledge, store, memory, signals)
    finally:
        store.close()
    print("bye.")


def _loop(
    orchestrator: Orchestrator,
    knowledge: Knowledge,
    store: StructuredStore,
    memory: MemoryStore,
    signals: SignalLog,
) -> None:
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
        # One guard covers all paths so a backend failure prints an error and the REPL survives.
        kind, payload = "query", {}
        try:
            if text.startswith(":"):
                kind = "command"
                command = text[1:].partition(" ")[0].lower()
                payload = {"command": command}
                # Briefing needs knowledge + the LLM, which live here in the loop, not in
                # _handle_command (whose commands only touch the stores).
                if command in ("brief", "briefing"):
                    _handle_brief(store, knowledge, orchestrator)
                else:
                    _handle_command(text, store, memory)
            else:
                payload = _answer(text, knowledge, orchestrator)
        except Exception as exc:  # keep the REPL alive if a backend call fails
            print(f"[error] {_redact(str(exc))}")
            payload = {**payload, "error": type(exc).__name__}
        # Signal capture (Core Stage 1): every turn is logged, append-only, best-effort.
        signals.emit(kind, payload)


def _answer(text: str, knowledge: Knowledge, orchestrator: Orchestrator) -> dict:
    result = knowledge.ask(text)
    if result is None:
        # No connector applied -> labeled plain chat (clearly the model's own knowledge).
        print(f"jarvis (chat)> {orchestrator.chat(text).strip()}")
        return {"path": "chat"}
    marker = " (cached)" if result.cached else ""
    print(f"jarvis{marker}> {result.text}")
    return {"path": "knowledge", "cached": result.cached}


# What the briefing pulls from the Phase-1 knowledge pipeline. Fixed for Phase 2; goal-derived
# digests are a later refinement.
_DIGEST_QUERY = "What are today's top market and tech news headlines?"


def _handle_brief(store: StructuredStore, knowledge: Knowledge, orchestrator: Orchestrator) -> None:
    now = datetime.now().astimezone()
    # The two non-deterministic sources (calendar = network/token, digest = router LLM + connectors)
    # are best-effort: a failure degrades that section to empty rather than killing the briefing.
    # Goals are local + deterministic, so they always render.
    goals = store.get_goals(status="active")
    data = BriefingData(
        when=now, events=_brief_events(now), goals=goals, digest=_brief_digest(knowledge)
    )
    print(phrase(data, orchestrator.chat))


def _brief_events(now: datetime) -> list:
    from jarvis.calendar.client import connect, day_bounds

    try:
        client = connect()
        return client.list_events(*day_bounds(now)) if client is not None else []
    except Exception:
        return []  # calendar unreachable -> no events section, briefing still renders


def _brief_digest(knowledge: Knowledge) -> str | None:
    try:
        answer = knowledge.ask(_DIGEST_QUERY)
        return answer.text if answer else None
    except Exception:
        return None  # digest unavailable -> empty section, briefing still renders


def _handle_agenda() -> None:
    # Imported lazily so the google libs only load when the calendar is actually used.
    from jarvis.calendar.client import connect, day_bounds

    client = connect()
    if client is None:
        print("calendar not connected. Run:  python -m jarvis calendar-auth")
        return
    time_min, time_max = day_bounds(datetime.now().astimezone())
    events = client.list_events(time_min, time_max)
    if not events:
        print("(no events today)")
        return
    for event in events:
        when = "all day" if event.all_day else f"{event.start:%H:%M}-{event.end:%H:%M}"
        location = f"  @ {event.location}" if event.location else ""
        print(f"  {when}  {event.summary}{location}")


def _handle_goal(argument: str, store: StructuredStore) -> None:
    sub, _, rest = argument.partition(" ")
    sub, rest = sub.lower(), rest.strip()
    if sub == "add":
        if not rest:
            print("usage: :goal add <text>")
            return
        goal = store.save_goal(rest)
        print(f"added goal #{goal.id}")
    elif sub == "done":
        if not rest.isdigit():
            print("usage: :goal done <id>")
            return
        goal = store.update_goal(int(rest), status="done", progress=1.0)
        print(f"goal #{goal.id} done")
    else:
        print("usage: :goal add <text> | :goal done <id>")


def _handle_command(
    text: str,
    store: StructuredStore,
    memory: MemoryStore,
) -> None:
    command, _, argument = text[1:].partition(" ")
    command = command.lower()
    argument = argument.strip()
    if command == "note":
        if not argument:
            print("usage: :note <text>")
            return
        # Explicit :note is a deliberate "remember", so importance is bumped. If embedding fails
        # nothing is written (save embeds before it upserts), so the store never half-commits.
        memory.remember(argument, explicit=True)
        print("saved to memory")
    elif command == "notes":
        records = memory.all()
        if not records:
            print("(no memories yet)")
            return
        for record in records:
            print(f"  {record.content}")
    elif command == "recall":
        if not argument:
            print("usage: :recall <query>")
            return
        results = memory.retrieve(argument, k=5)
        if not results:
            print("(no matches)")
            return
        for record in results:
            print(f"  {record.content}")
    elif command == "goal":
        _handle_goal(argument, store)
    elif command == "goals":
        goals = store.get_goals()
        if not goals:
            print("(no goals yet)")
            return
        for goal in goals:
            mark = "x" if goal.status == "done" else " "
            print(f"  [{mark}] #{goal.id}  {goal.description}")
    elif command in ("cal", "agenda"):
        _handle_agenda()
    elif command == "signals":
        events = store.get_signals(limit=20)
        if not events:
            print("(no signals yet)")
            return
        for event in events:
            print(f"  {event.ts:%H:%M:%S}  {event.kind}  {event.payload}")
    else:
        print(f"unknown command: :{command}")
