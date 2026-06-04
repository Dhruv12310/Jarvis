"""Finance (Phase 4): local transaction tracking with a deterministic Tier-0 analysis engine.

The defining rule: EVERY financial figure is computed by deterministic code (`engine.py`); the LLM
never sums, estimates, or infers a number - it only classifies a merchant string, parses a question,
and phrases an already-computed result. Money is `decimal.Decimal`, never float. Transactions live
locally in the StructuredStore; the import path is fully local. Jarvis reads/tracks only - it never
moves money and never gives advice.
"""
