# Phase 4 — TODO

Tracking list for `/build`. One vertical slice per commit. Full detail in `tasks/plan.md`.
**Every financial figure is computed by deterministic code; the LLM only classifies a merchant string,
parses a question, and phrases a computed result — it NEVER sums a number.** Money is `Decimal`.
Reads/tracks only — never moves money, never gives advice. (Phases 0–3 shipped; todos in git history.)

---

## [x] Slice 1 — Model + finance store + CSV/OFX import  ·  `feat(finance): transaction model + local CSV/OFX import into the structured store`   [OQ1: import + Plaid, both built]
- [x] (source-driven) verified `ofxtools` parse API (OFXTree().parse->convert; trnamt/ledgerbal already Decimal)
- [x] `finance/transaction.py` — `Transaction(id, date, amount: Decimal, merchant, category, account)` + `Account(...)` + `make_id`; money is Decimal
- [x] `finance/sources/` — `TransactionSource` ABC `load()`; `CsvSource` (stdlib), `OfxSource` (only ofxtools importer); signs normalized; `id` = hash(account,date,amount,merchant)
- [x] `stores` — `save_transactions` (idempotent INSERT OR IGNORE on id), `get_transactions(start?,end?,category?,account?)`, accounts; amount stored as TEXT
- [x] `__main__.py` — `python -m jarvis import <file>`; pyproject += `ofxtools`; boundary guard: ofxtools (+plaid) only under `finance/`
- [x] Verify: `test_finance_store.py` (round-trip + idempotent re-import + filters); `test_finance_sources.py` (CSV+OFX→Decimal, signs); import smoke (3 new→0); 203 green; ruff clean

### ▸ Checkpoint: real data in, locally

## [x] Slice 2 — Deterministic finance engine  ·  `feat(finance): deterministic Tier-0 finance engine (no LLM on the math path)`
- [x] `finance/engine.py` (imports NO LLM) — spending by category/period, total, net worth, period-over-period (delta+pct), recurring detection, budget-vs-actual; every return a Decimal
- [x] `finance/transaction.py` += `Budget`, `BudgetStatus`, `Recurring`; `stores` save/get budgets
- [x] boundary guard: `engine.py` imports no `llm`/`ollama` (structural proof of the absolute constraint)
- [x] Verify: `test_finance_engine.py` — every function vs fixtures, LLM absent, exact Decimals, reproducible; recurring + budget math

## [x] Slice 3 — Categorization (rules + LLM fallback; correctable)  ·  `feat(finance): deterministic categorization with an LLM fallback for unknown merchants`
- [x] `finance/categorize.py` — fixed category set; merchant→category rules; override lookup; unknown → LLM classifies the merchant STRING (JSON-constrained); precedence override > rule > LLM > uncategorized
- [x] `stores` — `save_category_override`/`get_category_overrides`/`recategorize_merchant`; `service.recategorize` + `:recat` persists + re-categorizes; import categorizes on ingest (rules+overrides, no LLM)
- [x] Verify: `test_categorize.py` — rule hit; override beats rule; unknown → fake LLM (sees only the string, no amount); correction persists + signal carries no merchant

## [x] Slice 4 — Finance Q&A + briefing  ·  `feat(finance): finance Q&A + briefing (engine computes, LLM only phrases)`
- [x] `finance/qa.py` — LLM parse → `FinanceQuery{metric, category?, period?}` (validated); engine computes; LLM phrases the EXACT figure (no recompute)
- [x] `service.py` `finance_answer` (metric-only signal, no amounts) + `categorize_unknowns` + `accounts`/`set_budget`/`budget_status`; `cli.py` `:spend`/`:accounts`/`:budget`/`:categorize`; GUI Finance shortcut; briefing finance line
- [x] Verify: `test_finance_qa.py` — fake LLM; answer figure == engine output (no model-invented number); signal carries no amount; briefing finance line + GUI finance card

### ▸ Checkpoint: Phase 4 feature-complete → `/test` → `/review` → `/code-simplify` → `/ship` → record learnings in docs/DECISIONS.md

## [x] Slice 5 — Plaid source  ·  `feat(finance): Plaid transaction source behind the source interface (opt-in, gated)`   [OQ1: opt-in automation]
- [x] (source-driven) verified `plaid-python` 39 API (Configuration/PlaidApi, transactions_sync, accounts_get; amount sign = positive-outflow)
- [x] `finance/sources/plaid_source.py` (only plaid importer, boundary-guarded) — same `load()` contract; `_normalize` flips Plaid's sign to ours
- [x] `config` Plaid client_id/secret/access_token/env via `.env`; `__main__` `import --plaid` (token-gated); pyproject += `plaid-python`; boundary guard covers plaid; `docs/plaid-setup.md`
- [x] Verify: `test_plaid_source.py` (normalize a fake Plaid response, sign flip, no network) + `@integration` gated on token; **live verification PENDING user's Plaid creds**
