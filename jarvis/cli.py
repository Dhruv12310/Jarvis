"""Plain CLI for Jarvis.

Free-text questions go through the knowledge pipeline (route -> deterministic fetch -> grounded,
cited summary). When no connector applies it falls back to labeled plain chat. Lines starting with
``:`` are store commands: :note/:notes/:recall (now backed by the memory store) and :signals.
"""

from __future__ import annotations

import re

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
    "Commands:  :note <text>  |  :notes  |  :recall <query>  |  :signals  |  exit"
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
                payload = {"command": text[1:].partition(" ")[0].lower()}
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
    elif command == "signals":
        events = store.get_signals(limit=20)
        if not events:
            print("(no signals yet)")
            return
        for event in events:
            print(f"  {event.ts:%H:%M:%S}  {event.kind}  {event.payload}")
    else:
        print(f"unknown command: :{command}")
