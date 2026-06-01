"""Plain CLI for Jarvis.

Free-text questions go through the knowledge pipeline (route -> deterministic fetch -> grounded,
cited summary). When no connector applies it falls back to labeled plain chat. Lines starting with
``:`` are Phase 0 store commands (:note, :notes, :recall).
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
from jarvis.llm.embedder import Embedder, OllamaEmbedder
from jarvis.orchestrator import Orchestrator
from jarvis.stores.chroma_store import ChromaVectorStore
from jarvis.stores.sqlite_store import SQLiteStructuredStore
from jarvis.stores.structured import StructuredStore
from jarvis.stores.vector import VectorStore

BANNER = (
    "Jarvis (Phase 1). Ask about markets, AI/business news, or HN/YC and answers come from live\n"
    "sources with citations. General questions fall back to plain chat.\n"
    "Commands:  :note <text>  |  :notes  |  :recall <query>  |  exit"
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


def run() -> None:
    config.ensure_dirs()
    llm = OllamaClient()
    orchestrator = Orchestrator(llm)
    knowledge = _build_knowledge(llm)
    store = SQLiteStructuredStore(config.db_path)
    vector = ChromaVectorStore(config.vector_dir)
    embedder = OllamaEmbedder()
    print(BANNER)
    try:
        _loop(orchestrator, knowledge, store, vector, embedder)
    finally:
        store.close()
    print("bye.")


def _loop(
    orchestrator: Orchestrator,
    knowledge: Knowledge,
    store: StructuredStore,
    vector: VectorStore,
    embedder: Embedder,
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
        try:
            if text.startswith(":"):
                _handle_command(text, store, vector, embedder)
            else:
                _answer(text, knowledge, orchestrator)
        except Exception as exc:  # keep the REPL alive if a backend call fails
            print(f"[error] {exc}")


def _answer(text: str, knowledge: Knowledge, orchestrator: Orchestrator) -> None:
    result = knowledge.ask(text)
    if result is None:
        # No connector applied -> labeled plain chat (clearly the model's own knowledge).
        print(f"jarvis (chat)> {orchestrator.chat(text).strip()}")
        return
    marker = " (cached)" if result.cached else ""
    print(f"jarvis{marker}> {result.text}")


def _handle_command(
    text: str,
    store: StructuredStore,
    vector: VectorStore,
    embedder: Embedder,
) -> None:
    command, _, argument = text[1:].partition(" ")
    command = command.lower()
    argument = argument.strip()
    if command == "note":
        if not argument:
            print("usage: :note <text>")
            return
        # Embed first, then save, then add: a backend failure leaves no half-written note,
        # so the structured store and the vector store never diverge.
        embedding = embedder.embed(argument)
        note = store.save_note(argument)
        vector.add(id=str(note.id), text=argument, embedding=embedding)
        print(f"saved note #{note.id}")
    elif command == "notes":
        notes = store.get_notes()
        if not notes:
            print("(no notes yet)")
            return
        for note in notes:
            print(f"  #{note.id}  {note.content}")
    elif command == "recall":
        if not argument:
            print("usage: :recall <query>")
            return
        hits = vector.query(embedder.embed(argument), k=5)
        if not hits:
            print("(no matches)")
            return
        for hit in hits:
            print(f"  #{hit.id}  (d={hit.distance:.3f})  {hit.text}")
    else:
        print(f"unknown command: :{command}")
