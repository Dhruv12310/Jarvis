"""Entry point for ``python -m jarvis``.

Usage:
    python -m jarvis              chat REPL
    python -m jarvis ui           desktop GUI (chat + Jarvis feed)
    python -m jarvis voice        push-to-talk voice loop (local STT + TTS)
    python -m jarvis import <f>   import transactions from a local CSV/OFX/QFX file
    python -m jarvis import --plaid  sync transactions from Plaid (opt-in; needs .env creds)
    python -m jarvis reflect      run reflection once (Brain job): synthesize insights about you
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
    if args and args[0] == "ui":
        # Flet stays under jarvis.ui (boundary-guarded); this entry point never imports it directly.
        from jarvis.cli import build_service
        from jarvis.ui.app import launch

        service, store = build_service(source="gui")
        try:
            launch(service)
        finally:
            store.close()
        return 0
    if args and args[0] == "import":
        # Fully local: read a bank export, normalize, and store. No network, no LLM.
        if len(args) < 2:
            print("usage: python -m jarvis import <file.csv|file.ofx|file.qfx>")
            return 1
        from jarvis.config import config
        from jarvis.finance.categorize import Categorizer, categorize_transactions
        from jarvis.stores.sqlite_store import SQLiteStructuredStore

        config.ensure_dirs()
        if args[1] == "--plaid" and not config.plaid_access_token:
            print("Plaid not configured. Set JARVIS_PLAID_* in .env (docs/plaid-setup.md).")
            return 1
        try:
            if args[1] == "--plaid":
                from jarvis.finance.sources.plaid_source import (
                    PlaidSource,  # lazy: only loads plaid here
                )

                transactions, accounts = PlaidSource().load()
            else:
                from jarvis.finance.sources import source_for

                transactions, accounts = source_for(args[1]).load()
            store = SQLiteStructuredStore(config.db_path)
            try:
                # Categorize deterministically (rules + saved corrections) at import - no LLM.
                # Unknown merchants stay "uncategorized"; the LLM fills them on demand later.
                categorizer = Categorizer(overrides=store.get_category_overrides())
                transactions = categorize_transactions(transactions, categorizer)
                added = store.save_transactions(transactions)
                for account in accounts:
                    store.save_account(account)
            finally:
                store.close()
        except Exception as exc:  # never let a raw traceback (esp. a Plaid error) hit the terminal
            from jarvis.redact import redact

            print(f"import failed: {redact(str(exc))}")
            return 1
        print(
            f"imported {added} new transaction(s) from {len(transactions)} row(s); "
            f"{len(accounts)} account(s)"
        )
        return 0
    if args and args[0] == "reflect":
        # Reflection is a Brain job (LLM synthesis): run it once on demand, then exit.
        from jarvis.cli import build_service

        service, store = build_service(source="cli")
        try:
            print(f"reflected: {service.reflect(force=True)} insight(s)")
        finally:
            store.close()
        return 0
    if args and args[0] == "voice":
        # Voice libs stay under jarvis.voice (boundary-guarded). STT + TTS are local.
        from jarvis.cli import build_service
        from jarvis.config import config
        from jarvis.voice.loop import run_voice_loop
        from jarvis.voice.stt import FasterWhisperSTT

        service, store = build_service(source="voice")
        tts = None
        if config.tts_model_path.exists():
            from jarvis.voice.tts import PiperTTS

            tts = PiperTTS()
        else:
            print(f"(no TTS voice at {config.tts_model_path}; running voice-to-text only)")
        try:
            run_voice_loop(service, FasterWhisperSTT(), tts)
        finally:
            store.close()
        return 0
    from jarvis.cli import run

    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
