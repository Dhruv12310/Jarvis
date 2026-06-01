"""Plain CLI chat loop for Jarvis Phase 0.

Wires the Ollama-backed orchestrator and the structured store to stdin/stdout. Plain text is a chat
turn; a line starting with ``:`` is a command. Slice C adds ``:recall`` and makes ``:note`` embed.
"""

from __future__ import annotations

from jarvis.config import config
from jarvis.llm.client import OllamaClient
from jarvis.orchestrator import Orchestrator
from jarvis.stores.sqlite_store import SQLiteStructuredStore
from jarvis.stores.structured import StructuredStore

BANNER = (
    "Jarvis (Phase 0). Type a message to chat.\n"
    "Commands:  :note <text>  save a note   |   :notes  list notes   |   exit"
)


def run() -> None:
    config.ensure_dirs()
    orchestrator = Orchestrator(OllamaClient())
    store = SQLiteStructuredStore(config.db_path)
    print(BANNER)
    try:
        _loop(orchestrator, store)
    finally:
        store.close()
    print("bye.")


def _loop(orchestrator: Orchestrator, store: StructuredStore) -> None:
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
            _handle_command(text, store)
            continue
        try:
            reply = orchestrator.chat(text)
        except Exception as exc:  # keep the REPL alive if the backend hiccups
            print(f"[error] {exc}")
            continue
        print(f"jarvis> {reply.strip()}")


def _handle_command(text: str, store: StructuredStore) -> None:
    command, _, argument = text[1:].partition(" ")
    command = command.lower()
    argument = argument.strip()
    if command == "note":
        if not argument:
            print("usage: :note <text>")
            return
        note = store.save_note(argument)
        print(f"saved note #{note.id}")
    elif command == "notes":
        notes = store.get_notes()
        if not notes:
            print("(no notes yet)")
            return
        for note in notes:
            print(f"  #{note.id}  {note.content}")
    else:
        print(f"unknown command: :{command}")
