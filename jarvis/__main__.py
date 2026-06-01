"""Entry point for ``python -m jarvis``.

Usage:
    python -m jarvis            chat REPL
    python -m jarvis selftest   run the Phase 0 Definition-of-Done self-test
"""

from __future__ import annotations

import sys


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "selftest":
        from jarvis.selftest import main as selftest_main

        return selftest_main()
    from jarvis.cli import run

    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
