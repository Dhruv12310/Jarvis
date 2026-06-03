"""Entry point for ``python -m jarvis``.

Usage:
    python -m jarvis              chat REPL
    python -m jarvis selftest     run the Phase 0 Definition-of-Done self-test
    python -m jarvis calendar-auth  one-time Google Calendar OAuth (read-only)
"""

from __future__ import annotations

import sys


def main() -> int:
    # The local model freely emits emoji/Unicode; force UTF-8 so a Windows cp1252 console can't
    # raise UnicodeEncodeError mid-print (e.g. on a briefing). No-op where stdout already copes.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if args and args[0] == "selftest":
        from jarvis.selftest import main as selftest_main

        return selftest_main()
    if args and args[0] == "calendar-auth":
        from jarvis.calendar.oauth import authorize
        from jarvis.config import config

        authorize()
        print(f"authorized; token saved to {config.google_token_path}")
        return 0
    from jarvis.cli import run

    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
