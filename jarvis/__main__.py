"""Entry point for ``python -m jarvis``.

Slice D adds a ``selftest`` subcommand here; for now the only action is the chat REPL.
"""

from __future__ import annotations

from jarvis.cli import run

if __name__ == "__main__":
    run()
