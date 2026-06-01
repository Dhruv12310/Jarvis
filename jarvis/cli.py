"""Plain CLI chat loop for Jarvis Phase 0.

Wires the Ollama-backed orchestrator and both stores to stdin/stdout. Plain text is a chat turn;
a line starting with ``:`` is a command (``:note``, ``:notes``, ``:recall``).
"""

from __future__ import annotations

from jarvis.config import config
from jarvis.llm.client import OllamaClient
from jarvis.llm.embedder import Embedder, OllamaEmbedder
from jarvis.orchestrator import Orchestrator
from jarvis.stores.chroma_store import ChromaVectorStore
from jarvis.stores.sqlite_store import SQLiteStructuredStore
from jarvis.stores.structured import StructuredStore
from jarvis.stores.vector import VectorStore

BANNER = (
    "Jarvis (Phase 0). Type a message to chat.\n"
    "Commands:  :note <text>  save and embed a note   |   :notes  list notes\n"
    "           :recall <query>  find similar notes    |   exit"
)


def run() -> None:
    config.ensure_dirs()
    orchestrator = Orchestrator(OllamaClient())
    store = SQLiteStructuredStore(config.db_path)
    vector = ChromaVectorStore(config.vector_dir)
    embedder = OllamaEmbedder()
    print(BANNER)
    try:
        _loop(orchestrator, store, vector, embedder)
    finally:
        store.close()
    print("bye.")


def _loop(
    orchestrator: Orchestrator,
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
        if text.startswith(":"):
            _handle_command(text, store, vector, embedder)
            continue
        try:
            reply = orchestrator.chat(text)
        except Exception as exc:  # keep the REPL alive if the backend hiccups
            print(f"[error] {exc}")
            continue
        print(f"jarvis> {reply.strip()}")


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
        note = store.save_note(argument)
        vector.add(id=str(note.id), text=argument, embedding=embedder.embed(argument))
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
            print(f"  #{hit.id}  ({hit.score:.3f})  {hit.text}")
    else:
        print(f"unknown command: :{command}")
