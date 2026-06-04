# Plan: Jarvis — Phase 4 (Finance)

Source-of-truth: `SPEC.md` (this phase) + `CLAUDE.md` invariants + `docs/Jarvis_Core_Spec.md` (§4
deterministic-vs-LLM boundary; §5.2 finance in the StructuredStore). One vertical slice per commit.
The defining rule: **every financial figure is computed by deterministic Tier-0 code; the LLM only
classifies a merchant string, parses a question, and phrases a computed result — it never sums a
number.** Phases 0–3 are shipped (plans in git history).

```
Slice 1   Model + store + import   Transaction/Account (Decimal) + finance store + CSV/OFX import (local)
        |
Slice 2   Deterministic engine     spending/balances/trends/recurring/budgets - pure, NO LLM (the proof)
        |
Slice 3   Categorization           rules + override store + LLM fallback (merchant string only); corrects
        |
Slice 4   Finance Q&A + briefing    LLM parse -> engine compute -> LLM phrase; :spend; briefing line
        |
Slice 5   Plaid source              opt-in automation behind the same interface (OQ1: import + Plaid)
```

Order: Slice 1 (data in) → Slice 2 (the math) → Slice 3 (labels) → Slice 4 (ask/surface) → Slice 5
(Plaid, opt-in second source). Slices 1–4 are the local path (the everyday default); the engine (2) is
the heart and is source-agnostic, so Plaid (5) plugs in without touching it.

Dependency graph:
- Slice 1 (model+store+import) ← nothing; produces normalized rows.
- Slice 2 (engine) ← Slice 1 (operates on stored transactions). The boundary guard lands here.
- Slice 3 (categorize) ← Slice 1 (labels transactions; engine groups by them).
- Slice 4 (Q&A+briefing) ← Slices 2 + 3 (compute + categorized) + the Phase 3 facade/briefing.

---

## Task List

### Slice 1 — Transaction model + finance store + CSV/OFX import  [local data in]
**Source-driven first:** verify the current `ofxtools` parse API (`OFXTree().parse` → statement →
transactions; `TRNAMT`/`DTPOSTED`/`NAME`/`MEMO`, `LEDGERBAL`) and a representative bank CSV shape.

**Acceptance:**
- [ ] `finance/transaction.py`: frozen `Transaction(id, date, amount: Decimal, merchant, category,
  account)` + `Account(id, name, type, balance: Decimal)`. Money is **Decimal**, never float.
- [ ] `finance/sources/base.py`: `TransactionSource` (ABC) `load() -> (list[Transaction], list[Account])`.
  `csv_source.py` (stdlib csv), `ofx_source.py` (the ONLY `ofxtools` importer). Signs normalized
  (negative = outflow); `id` = deterministic hash(account, date, amount, merchant).
- [ ] `stores/structured.py` + `sqlite_store.py`: `save_transactions` (idempotent — dedup on `id`),
  `get_transactions(start?, end?, category?, account?)`, `save_account`/`get_accounts`. Amount stored as
  TEXT (exact Decimal). Raw SQL stays in `sqlite_store.py`.
- [ ] `__main__.py`: `python -m jarvis import <file.csv|file.ofx>` → source.load → save (reports counts).
- [ ] pyproject += `ofxtools`; approved-deps += `ofxtools`; boundary test: `ofxtools` only under `finance/`.

**Verification:** `test_finance_store.py` (round-trip + idempotent re-import inserts each row once);
`test_finance_sources.py` (CSV + OFX fixture → Decimal amounts, correct signs, no network). Full suite
green; `ruff` clean.
**Files:** `finance/{__init__,transaction}.py`, `finance/sources/{__init__,base,csv_source,ofx_source}.py`,
`stores/structured.py`, `stores/sqlite_store.py`, `__main__.py`, `pyproject.toml`, tests. **Scope:** L.
**Commit:** `feat(finance): transaction model + local CSV/OFX import into the structured store`

### ▸ Checkpoint: real data in, locally
- [ ] Importing a bank export yields normalized, deduped Decimal transactions in SQLite; nothing left the machine.

### Slice 2 — Deterministic finance engine  [the proof: no LLM on the math path]
**Acceptance:**
- [ ] `finance/engine.py` (pure; imports **no** LLM): `spending_by_category(txns, start, end)`,
  `spending_by_period(txns, period)`, `total_spending(txns, start, end)`, `net_worth(accounts)`,
  `period_over_period(...) -> (delta, pct)`, `recurring_charges(txns)`, `budget_vs_actual(txns, budgets)`.
  Every return is a `Decimal` (or a struct of Decimals).
- [ ] `finance/transaction.py` += `Budget(category, limit: Decimal, period)` + `BudgetStatus`/`Recurring`.
- [ ] `stores`: `save_budget`/`get_budgets` (for slice 4 surfacing; table here).
- [ ] Boundary test: `engine.py` imports no `llm`/`ollama` (structural proof of the absolute constraint).

**Verification:** `test_finance_engine.py` — every function against **fixture transactions** with the
**LLM absent**; assert exact Decimal values; reproducibility (same fixtures → identical figures);
recurring detection on a crafted cadence; budget-vs-actual math. **Files:** `finance/engine.py`,
`finance/transaction.py`, `stores/*`, `tests/test_finance_engine.py`, `tests/test_boundaries.py`. **Scope:** L.
**Commit:** `feat(finance): deterministic Tier-0 finance engine (no LLM on the math path)`

### Slice 3 — Categorization (rules + LLM fallback; correctable)
**Acceptance:**
- [ ] `finance/categorize.py`: a fixed category set; deterministic merchant→category rules; an override
  store lookup. For an UNKNOWN merchant, the LLM classifies the merchant **string** into the set (JSON-
  constrained, like the router) — never touches an amount. Precedence: override > rule > LLM > uncategorized.
- [ ] `stores`: `save_category_override(merchant, category)` / `get_category_overrides()`; a `:recat`
  correction applies the override AND updates stored transactions for that merchant (persists).
- [ ] Import (slice 1) now categorizes on ingest via this module.

**Verification:** `test_categorize.py` — rule hit; **override beats rule**; unknown → **fake LLM**
classifies (asserts the LLM saw only the merchant string, no amount); a correction persists and re-
categorizes. **Files:** `finance/categorize.py`, `stores/*`, `cli.py`, `tests/test_categorize.py`. **Scope:** M.
**Commit:** `feat(finance): deterministic categorization with an LLM fallback for unknown merchants`

### Slice 4 — Finance Q&A + briefing integration
**Acceptance:**
- [ ] `finance/qa.py`: LLM parses the question → `FinanceQuery{metric, category?, period?}` (JSON schema,
  validated); the **engine** computes from `get_transactions(filtered)`; the LLM **phrases** the exact
  computed figure (given the number — it does not recompute).
- [ ] `service.py`: `finance_answer(question) -> str` (emits a metadata-only signal — no amounts).
  `cli.py`: `:spend <q>` / `:accounts` / `:budget`; a GUI finance shortcut (Phase 3 surface).
- [ ] Briefing: a deterministic finance line (e.g. month-to-date spend + top category) assembled by the
  engine, phrased by the LLM, presented as computed-from-my-data.

**Verification:** `test_finance_qa.py` — with a **fake LLM**, parse→engine→phrase; assert the figure in
the answer equals the **engine's** output (no model-invented number) and the engine ran with no LLM;
briefing includes the finance line. **Files:** `finance/qa.py`, `service.py`, `cli.py`, `briefing.py`,
`tests/test_finance_qa.py`. **Scope:** M.
**Commit:** `feat(finance): finance Q&A + briefing (engine computes, LLM only phrases)`

### ▸ Checkpoint: Phase 4 complete (local import → engine → categorize → ask/brief)
- [ ] Numbers verifiably from the engine; LLM never on the math path (boundary + unit proof); reads-only,
  no advice. Proceed `/test` → `/review` → `/code-simplify` → `/ship`, recording learnings to DECISIONS.

### Slice 5 — Plaid source  [OQ1: opt-in automation behind the same interface]
**Source-driven first:** verify current Plaid sandbox/production tiers, `/transactions/sync`, the
`plaid-python` client, and the auth/access-token flow against current Plaid docs.
**Acceptance:**
- [ ] `finance/sources/plaid_source.py`: `PlaidSource` (the ONLY plaid importer, boundary-guarded) with
  the same `load() -> (transactions, accounts)` contract — the engine is unchanged. Normalizes Plaid
  transactions/accounts to the Decimal model (signs correct).
- [ ] `config`: Plaid `client_id`/`secret`/`access_token` via `.env` (git-ignored, never committed,
  redacted from errors). `__main__.py`: `import --plaid` (or a `plaid-sync`) path through the source.
- [ ] pyproject += `plaid-python`; approved-deps += it; boundary guard: `plaid` only under `finance/`.
- [ ] Docs: a short Plaid setup note (create app, sandbox vs production, obtain an access token).

**Verification:** `test_plaid_source.py` — normalize a **fake Plaid API response** (no network) into the
Decimal model; an `@integration` test gated on a configured token (skips like OAuth). Live verification
(`/transactions/sync` against the user's Plaid item) is **PENDING the user's Plaid credentials**.
**Files:** `finance/sources/plaid_source.py`, `config.py`, `__main__.py`, `pyproject.toml`, docs,
`tests/test_plaid_source.py`, `tests/test_boundaries.py`. **Scope:** M.
**Commit:** `feat(finance): Plaid transaction source behind the source interface (opt-in, gated)`

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM computes/estimates a figure (hallucinated money) | Critical (harm) | Engine is pure + imports no LLM (boundary test); Q&A asserts the answer figure == engine output; LLM only parses/phrases |
| Float money rounding errors | High | `Decimal` everywhere; stored as TEXT; engine sums Decimals; asserted exact in tests |
| Re-import duplicates transactions | High | Deterministic `id` = hash(account,date,amount,merchant); dedup on conflict; idempotency test |
| Financial data leaks to logs / a third party | High | Local import (no egress); signals metadata-only (no amounts); redact errors; Plaid (if any) confined + token-gated |
| OFX/bank-CSV format variance | Med | `ofxtools` (standards-based) for OFX; CSV mapping configurable; fixtures for both; source behind interface |
| Scope creep into advice / money movement | Med | Hard Never list (reads/tracks only; facts not advice); enforced in phrasing prompts + review |
| Plaid balloons the phase | Med | Plaid is a DEFERRED optional slice; import-first is the complete local phase |

## Open Questions — RESOLVED with the user
- **OQ1 (data source)** — **import-first baseline + Plaid this phase** (both, behind one source
  interface; engine source-agnostic). Import is the local everyday path; Plaid is opt-in automation,
  confined + token-gated. Plaid's live verification needs the user's Plaid credentials.
- OQ2 categorization — rules + LLM fallback (classification of the merchant string only). OQ3 budgets —
  include (deterministic budget-vs-actual). Both confirmed.

## Parallelization
- Slice 1 is the barrier (no engine without data). Slices 2 (engine) and 3 (categorize) both depend only
  on Slice 1 and could parallelize across sessions; both touch the store, so serialize there. Slice 4
  needs 2 + 3 + the Phase 3 facade/briefing. Slice 5 (Plaid) plugs into the source interface independently.
