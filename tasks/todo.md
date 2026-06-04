# Phase 4 — TODO

Tracking list for `/build`. One vertical slice per commit. Full detail in `tasks/plan.md`.
**Every financial figure is computed by deterministic code; the LLM only classifies a merchant string,
parses a question, and phrases a computed result — it NEVER sums a number.** Money is `Decimal`.
Reads/tracks only — never moves money, never gives advice. (Phases 0–3 shipped; todos in git history.)

---

## [ ] Slice 1 — Model + finance store + CSV/OFX import  ·  `feat(finance): transaction model + local CSV/OFX import into the structured store`   [OQ1: import + Plaid, both built]
- [ ] (source-driven) verify `ofxtools` parse API + a bank CSV shape
- [ ] `finance/transaction.py` — `Transaction(id, date, amount: Decimal, merchant, category, account)` + `Account(...)`; money is Decimal
- [ ] `finance/sources/` — `TransactionSource` ABC `load()`; `CsvSource` (stdlib), `OfxSource` (only ofxtools importer); signs normalized; `id` = hash(account,date,amount,merchant)
- [ ] `stores` — `save_transactions` (idempotent dedup on id), `get_transactions(start?,end?,category?,account?)`, accounts; amount stored as TEXT
- [ ] `__main__.py` — `python -m jarvis import <file>`; pyproject += `ofxtools`; boundary guard: ofxtools only under `finance/`
- [ ] Verify: `test_finance_store.py` (round-trip + idempotent re-import); `test_finance_sources.py` (CSV+OFX fixture → Decimal, signs); full suite green; ruff clean

### ▸ Checkpoint: real data in, locally

## [ ] Slice 2 — Deterministic finance engine  ·  `feat(finance): deterministic Tier-0 finance engine (no LLM on the math path)`
- [ ] `finance/engine.py` (imports NO LLM) — spending by category/period, total, net worth, period-over-period (delta+pct), recurring detection, budget-vs-actual; every return a Decimal
- [ ] `finance/transaction.py` += `Budget`, `BudgetStatus`, `Recurring`; `stores` save/get budgets
- [ ] boundary guard: `engine.py` imports no `llm`/`ollama` (structural proof of the absolute constraint)
- [ ] Verify: `test_finance_engine.py` — every function vs fixtures, LLM absent, exact Decimals, reproducible; recurring + budget math

## [ ] Slice 3 — Categorization (rules + LLM fallback; correctable)  ·  `feat(finance): deterministic categorization with an LLM fallback for unknown merchants`
- [ ] `finance/categorize.py` — fixed category set; merchant→category rules; override lookup; unknown → LLM classifies the merchant STRING (JSON-constrained); precedence override > rule > LLM > uncategorized
- [ ] `stores` — `save_category_override`/`get_category_overrides`; `:recat` correction persists + re-categorizes; import categorizes on ingest
- [ ] Verify: `test_categorize.py` — rule hit; override beats rule; unknown → fake LLM (sees only the string, no amount); correction persists

## [ ] Slice 4 — Finance Q&A + briefing  ·  `feat(finance): finance Q&A + briefing (engine computes, LLM only phrases)`
- [ ] `finance/qa.py` — LLM parse → `FinanceQuery{metric, category?, period?}` (validated); engine computes; LLM phrases the EXACT figure (no recompute)
- [ ] `service.py` `finance_answer` (metadata-only signal, no amounts); `cli.py` `:spend`/`:accounts`/`:budget`; GUI finance shortcut; briefing finance line
- [ ] Verify: `test_finance_qa.py` — fake LLM; answer figure == engine output (no model-invented number); engine ran with no LLM; briefing includes the line

### ▸ Checkpoint: Phase 4 complete → `/test` → `/review` → `/code-simplify` → `/ship` → record learnings in docs/DECISIONS.md

## [ ] Slice 5 — Plaid source  ·  `feat(finance): Plaid transaction source behind the source interface (opt-in, gated)`   [OQ1: opt-in automation]
- [ ] (source-driven) verify Plaid sandbox/production tiers + `/transactions/sync` + `plaid-python` + auth
- [ ] `finance/sources/plaid_source.py` (only plaid importer, boundary-guarded) — same `load()` contract; normalize to Decimal model
- [ ] `config` Plaid client_id/secret/access_token via `.env` (redacted); `__main__` plaid path; pyproject += `plaid-python`; boundary guard: plaid only under `finance/`; docs setup note
- [ ] Verify: `test_plaid_source.py` (normalize a fake Plaid response, no network) + `@integration` gated on token; **live verification PENDING user's Plaid creds**
