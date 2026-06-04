# Spec: Jarvis — Phase 4 (Finance)

> Per-phase implementation spec for the **active** phase. Phases 0–3 are shipped; their specs live in
> `docs/specs/` and git history. Design source-of-truth: `CLAUDE.md` (invariants — Tier 0 deterministic
> engines, trust boundary) and **`docs/Jarvis_Core_Spec.md`** (§4 the deterministic-vs-LLM compute
> boundary; §5.2 finance is the data "whose corruption hurts most," lives in the `StructuredStore` as a
> `transactions` table). Phase 0–3 learnings: `docs/DECISIONS.md`.

## Objective

Jarvis tracks my money: it ingests my transactions, stores them **locally**, and answers questions
about spending, balances, and trends — with **every number computed by deterministic code**. Tracking
and analysis, not advice. Reactive only (no proactive finance nudges — that's Phase 5).

### THE defining constraint (strictest in the project)

**Every financial figure is computed by deterministic Tier-0 code.** The LLM NEVER computes, sums,
estimates, or infers a number. A hallucinated balance or budget figure is not a bug, it is **harm** —
finance is the entire reason Tier 0 exists, so this line is absolute. The LLM has exactly three jobs,
all language tasks, none touching an amount:
1. **classify a merchant *string*** into a category (like the Phase 1 router classifies a query),
2. **parse a natural-language finance question** into a structured `FinanceQuery` (metric + category +
   period), and
3. **phrase an already-computed result** into prose.

Enforced structurally: the finance **engine module imports no LLM** (a boundary test asserts it), and a
test proves finance answers are assembled from engine output, not model memory.

**Who it's for:** the single user (dbhatt24). Transactions are the **most sensitive data in the
project** — treated accordingly (local-only, redacted from logs, Decimal-exact).

### Assumptions (correct me before I build)

1. **Money is `Decimal`, never `float`.** Amounts are `decimal.Decimal`, stored in SQLite as **TEXT**
   (the exact decimal string), parsed back to `Decimal`. Float money is a correctness defect; the engine
   sums Decimals so totals are exact and reproducible.
2. **Signed amounts (OFX convention): negative = outflow/spend, positive = inflow.** "Spending on X" =
   the absolute value of the negative-amount transactions in category X over the period.
3. **Idempotent import:** a `Transaction.id` is a deterministic hash of (account, date, amount, merchant)
   so re-importing an overlapping export inserts each row once (dedup on conflict). Re-running the same
   query twice gives identical figures (the engine is pure + the data is stable).
4. **Source-agnostic engine.** A `TransactionSource` interface (pluggable, like `Connector`) feeds the
   engine; the math is identical whether rows came from a local import or Plaid. The data **source** is
   the one real privacy decision (OQ1).
5. **Categorization precedence:** user override > deterministic rule > LLM classification (unknown
   merchants only) > "uncategorized". A correction persists (a `merchant -> category` override table) so
   it sticks for future imports.
6. **Budgets (OQ3) are deterministic** budget-vs-actual (category + limit + period); the engine computes
   actual from transactions. No advice — it reports "spent X of Y", never "cut your dining".

## Trust boundary (sharpened — the most sensitive data in the system)

- **Transactions and ALL analysis live and run locally.** The CSV/OFX import path is **fully local — no
  egress**, ever (you export from your bank; nothing leaves the machine).
- The LLM calls (categorize a merchant string, parse a question, phrase a computed result) go to the
  **local Ollama** only. Computed figures + category labels reach only the local model — never the cloud.
- **Logs/signals are metadata-only:** no amounts, balances, or merchant strings in the signal log;
  financial data is **redacted from errors** (reuse `jarvis/redact.py`, extended).
- **Plaid (this phase, OQ1) is the ONLY outbound path** — confined to its own source module behind a
  boundary guard (like the Google libs under `calendar/`), token via `.env`/`data/`, never committed.
  Import remains fully local; Plaid is opt-in automation that the user accepted the third-party tradeoff
  for. The engine never knows or cares which source the rows came from.
- **Two hard safety boundaries (in Never):** Jarvis **reads/tracks only — it never moves money**, and it
  **reports facts — it does not give financial advice.**

## Tech Stack

| Concern | Choice | Why |
|---|---|---|
| Money type | `decimal.Decimal` (stdlib), stored as TEXT | Exact money math; float is a correctness defect |
| Transactions / accounts / budgets / overrides | `StructuredStore` (SQLite) | Core §5.2 - the data whose corruption hurts most; ACID |
| OFX/QFX import | **`ofxtools`** (zero external deps) | Maintained, standards-based OFX 1.6/2.03 + QFX; stdlib-only |
| CSV import | `csv` (stdlib) | Plain bank CSV exports |
| Finance engine (Tier 0) | pure Python, **no LLM import** | Every figure is code; boundary-guarded |
| Categorization fallback | local Ollama `LLMClient` (existing) | Classify merchant STRING only (constrained, like routing) |
| Q&A parse + phrasing | local Ollama `LLMClient` (existing) | Parse NL -> FinanceQuery; phrase computed results |
| Source (this phase) | Plaid (`plaid-python`) behind `TransactionSource` | OQ1 - opt-in automation; the only outbound path, confined + token-gated |

**New runtime deps (Phase 4):** `ofxtools` (import slice) + `plaid-python` (Plaid slice, confined to its
source module behind a boundary guard). No other new deps.

## Commands

```bash
python -m jarvis import <file.csv|file.ofx>   # local import -> normalized, deduped transactions
python -m jarvis                              # CLI: ask finance questions; :spend / :accounts / :budget
python -m jarvis ui                           # GUI: finance shortcut + cards (Phase 3 surface)

pytest -q                                     # offline: engine math vs fixtures, LLM absent
pytest -q -m integration                      # live: Plaid only if configured (gated like OAuth)
ruff check . ; ruff format --check .
```

## Project Structure

```
jarvis/
  finance/
    __init__.py
    transaction.py    # Transaction + Account + Budget value objects (Decimal money)
    sources/
      __init__.py
      base.py         # TransactionSource interface: load() -> (transactions, accounts)
      csv_source.py   # CsvSource (stdlib csv)
      ofx_source.py   # OfxSource (the ONLY ofxtools importer)
      plaid_source.py # PlaidSource (the ONLY plaid importer, behind a boundary guard; token via .env)
    engine.py         # DETERMINISTIC Tier-0 math. Imports NO LLM. The heart of the phase.
    categorize.py     # rules + override lookup; LLM fallback for unknown merchants (string only)
    qa.py             # parse NL -> FinanceQuery (LLM) -> engine compute -> phrase (LLM)
  stores/
    structured.py     # += save_transactions/get_transactions, accounts, budgets, category overrides
    sqlite_store.py   # += transactions/accounts/budgets/overrides tables (raw SQL stays here)
  service.py          # += finance_answer(); briefing pulls a finance line
  cli.py / __main__.py# += `import` subcommand; :spend / :accounts / :budget
tests/
  test_finance_engine.py   # the math vs fixture transactions, NO LLM (the core proof)
  test_finance_store.py    # transactions/accounts/budgets/overrides round-trip + idempotent import
  test_finance_sources.py  # CsvSource/OfxSource normalize a fixture file
  test_categorize.py       # rules + override precedence + LLM-fallback (fake LLM) + correction sticks
  test_finance_qa.py       # parse->engine->phrase with a fake LLM; figures come from the engine
  test_boundaries.py       # += engine imports no LLM; ofxtools only under finance/; (plaid if added)
```

## Code Style

The engine is pure and Decimal-exact; the LLM is nowhere near a number.

```python
# finance/transaction.py - money is Decimal, never float.
@dataclass(frozen=True)
class Transaction:
    id: str            # deterministic hash(account, date, amount, merchant) - idempotent import
    date: date
    amount: Decimal    # signed: negative = outflow/spend, positive = inflow
    merchant: str      # raw description/payee
    category: str      # assigned category, or "uncategorized"
    account: str

@dataclass(frozen=True)
class Account:
    id: str
    name: str
    type: str          # checking|savings|credit|...
    balance: Decimal
```

```python
# finance/engine.py - DETERMINISTIC. No LLM import anywhere in this module.
#   spending_by_category(txns, start, end) -> dict[str, Decimal]
#   spending_by_period(txns, period) -> dict[str, Decimal]      # period = month|week
#   total_spending(txns, start, end) -> Decimal
#   net_worth(accounts) -> Decimal                              # sum of balances
#   period_over_period(txns, ...) -> (Decimal delta, Decimal pct)
#   recurring_charges(txns) -> list[Recurring]                  # ~regular cadence + similar amount
#   budget_vs_actual(txns, budgets) -> list[BudgetStatus]       # actual computed from txns
# Every return is a Decimal (or a struct of Decimals). The LLM never sees this module.
```

```python
# finance/qa.py - the LLM parses + phrases; the engine computes. The model never sums.
#   1. parse:   LLM(question) -> FinanceQuery{metric, category?, period?}   (JSON schema, validated)
#   2. compute: engine.<metric>(get_transactions(filtered)) -> Decimal      (deterministic)
#   3. phrase:  LLM(question + the EXACT computed figure) -> prose          (no recomputation)
```

Conventions (carry forward): type hints, frozen dataclasses, `ABC`/`Protocol` seams, one config
location, conventional commits (no em-dashes, no attribution), ruff clean, commit per slice. Money is
`Decimal`; no raw SQL outside `sqlite_store.py`; the engine imports no LLM.

## Testing Strategy

- **Engine (unit, THE proof):** compute spending-by-category/period, totals, net worth, trends/%, and
  recurring detection against **fixture transactions** with the **LLM absent**; assert exact Decimal
  values. Reproducibility: the same fixtures give identical figures every run.
- **Store (unit):** transactions/accounts/budgets/overrides round-trip (temp SQLite); **idempotent
  import** (re-importing overlapping rows inserts each once via the deterministic id).
- **Sources (unit):** `CsvSource`/`OfxSource` normalize a small fixture file into `Transaction`s
  (Decimal amounts, signs correct); no network.
- **Categorize (unit):** rules hit; user **override beats rule**; unknown merchant -> **fake LLM**
  classifies into the fixed set (never touches an amount); a **correction persists**.
- **Q&A (unit):** with a **fake LLM**, parse -> engine -> phrase; assert the figure in the answer equals
  the **engine's** output (not a model-invented number), and that the engine ran with no LLM.
- **Boundary (extended):** the engine module imports no `llm`/`ollama`; `ofxtools` imported only under
  `finance/`; (Plaid lib only under `finance/` if added); no raw SQL outside `sqlite_store.py`.
- **Integration (`-m integration`):** Plaid gated on a configured token (skips like the keyed connectors
  / OAuth), only if OQ1 adds it.

## Boundaries

- **Always:**
  - Compute EVERY financial figure in deterministic code; the LLM only classifies a merchant string,
    parses a question into a `FinanceQuery`, and phrases code-computed results.
  - Money is `Decimal`; transactions/analysis are local; import is fully local (no egress).
  - Idempotent import (deterministic id); corrections persist; category precedence override > rule > LLM.
  - Storage behind interfaces (`StructuredStore`, `TransactionSource`, the engine as its own module);
    raw SQL only in `sqlite_store.py`; redact financial data from logs/errors.
  - `pytest` + `ruff` before each commit; conventional commits; commit per slice; CLI stays green.
- **Ask First:**
  - Any dependency beyond `ofxtools` + `plaid-python` (the two OQ1-approved source deps).
  - Changing the `StructuredStore` / `TransactionSource` interfaces once depended on.
- **Never:**
  - Let the LLM compute, sum, estimate, or infer ANY financial number.
  - **Move money / initiate a transaction** — Jarvis reads and tracks ONLY.
  - **Give financial, investment, or budgeting ADVICE** — report facts and trends; the user concludes.
  - Build Phase 5 (proactive finance nudges, "you're overspending", reflection/ranking); the Phase 6
    mobile finance view; cloud escalation / Model Router; send any transaction/balance off-machine
    (except a user-chosen Plaid source, confined + token-gated).

## Success Criteria (Definition of Done — testable)

1. **Data in, local + normalized:** `import <file>` ingests my transactions; they persist locally,
   normalized (Decimal), and re-import is idempotent.
2. **Numbers come from the engine:** spending/balance/trend questions return figures computed by the
   engine — the same query twice gives identical numbers, and a unit test asserts the engine's math
   against fixtures.
3. **Categorization:** rules + LLM fallback for unknown merchants assign categories; I can correct a
   category and it persists.
4. **Briefing:** finance figures appear in the briefing where relevant (e.g. month-to-date spend + top
   category), presented as computed-from-my-data.
5. **LLM is never on the math path:** the engine is fully unit-tested with the LLM absent; a boundary
   test asserts the engine imports no LLM; finance answers are assembled from engine output.
6. `pytest -q` passes fully offline; any live source (Plaid) is integration-gated; `selftest` PASS;
   `ruff` clean.

## Decisions (OPEN QUESTIONS — recommendations; OQ1 needs the user's eyes-open confirmation)

1. **DATA SOURCE (OQ1) — DECIDED (user, eyes open): import-first baseline + Plaid this phase.** Build
   the fully-local **CSV/OFX import** as the baseline (no third party; `ofxtools` zero-dep), AND wire
   **Plaid as an optional second source behind the same `TransactionSource` interface** this phase. The
   engine is **source-agnostic** — identical math either way. Plaid is the one outbound path: it routes
   transactions through a third-party aggregator (and Transactions is a paid subscription at scale), so
   it is **confined to its own source module behind a boundary guard, token via `.env`, integration-
   gated** (skips without credentials, like the keyed connectors / OAuth). Import is the everyday local
   path; Plaid is opt-in automation the user chose with the third-party tradeoff understood.
2. **CATEGORIZATION (OQ2) — RECOMMEND: rules + LLM fallback** for unknown merchants (classification of
   the merchant string only, never math), with corrections that persist.
3. **BUDGETS (OQ3) — RECOMMEND: include** deterministic budget-vs-actual this phase (high-value, pure
   math; reports "spent X of Y", never advice).

## Build-time verifications (source-driven-development, at the start of the relevant slice)

- **Import slice:** verify the current `ofxtools` parsing API (`OFXTree().parse(...)` / the parsed
  statement -> transactions, the OFX `TRNAMT`/`DTPOSTED`/`NAME`/`MEMO` fields and the `LEDGERBAL`) and a
  representative bank CSV shape, against current docs, before building the sources.
- **Plaid slice:** verify the current sandbox vs production tiers, `/transactions/sync`, and the auth
  flow against current Plaid docs.

## Build Order (for /plan to slice)

1. **Transaction/Account model + finance store + CSV/OFX import** — real data in, local + normalized +
   idempotent. `TransactionSource` interface + `CsvSource` + `OfxSource`; `import` command.
2. **Deterministic finance engine** — spending by category/period, totals, net worth, trends/%,
   recurring detection, budget-vs-actual. Pure, fully unit-tested, **no LLM**. Boundary guard.
3. **Categorization** — deterministic rules + override store + LLM fallback for unknown merchants;
   corrections persist; re-categorize.
4. **Finance Q&A + briefing** — facade `finance_answer` (LLM parse -> engine compute -> LLM phrase);
   `:spend`/`:accounts`/`:budget` + a GUI finance shortcut; finance line in the briefing.
5. **Plaid source** behind the same `TransactionSource` interface (OQ1: opt-in automation) — confined +
   boundary-guarded, token via `.env`, integration-gated; live verification needs the user's Plaid creds.

Then `/test` -> `/review` -> `/code-simplify` -> `/ship` per CLAUDE.md, recording learnings to
`docs/DECISIONS.md`.
