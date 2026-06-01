"""Plain CLI chat loop for Jarvis Phase 0.

Wires the Ollama-backed orchestrator to stdin/stdout. Slices B and C add the ``:note``, ``:notes``,
and ``:recall`` commands; for now it is a bare chat REPL.
"""

from __future__ import annotations

from jarvis.llm.client import OllamaClient
from jarvis.orchestrator import Orchestrator

BANNER = "Jarvis (Phase 0). Type a message; 'exit' or Ctrl-D to quit."


def run() -> None:
    orchestrator = Orchestrator(OllamaClient())
    print(BANNER)
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text.lower() in {"exit", "quit"}:
            break
        try:
            reply = orchestrator.chat(text)
        except Exception as exc:  # keep the REPL alive if the backend hiccups
            print(f"[error] {exc}")
            continue
        print(f"jarvis> {reply.strip()}")
    print("bye.")
