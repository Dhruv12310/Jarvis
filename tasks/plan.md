# Phase A — Stocks/company depth + cloud-escalation engine

## Goal
Give Jarvis genuine company depth (fundamentals: market cap, revenue, margins, P/E, 52-week,
analyst trend, recent company news) from the EXISTING Finnhub key, and stand up the Tier-2
cloud-escalation seam (Anthropic) for opt-in "Deep Dive" synthesis. Additive only; suite stays green.

## Invariants honored
- **Deterministic-first.** All figures/assembly/ranking are code; the LLM/cloud only phrase or
  synthesize. The deterministic `company()` view never calls a model.
- **Trust boundary.** Outbound HTTP stays in `connectors/` (Finnhub). The cloud is reached ONLY via
  the Model Router, which redacts (PII strip) before sending. Both are public-data paths.
- **Cloud is escalation-only / opt-in.** No key -> Deep Dive is gracefully disabled, never crashes.
- **Boundary tests stay green** and gain a new guard: `anthropic` importable only under `jarvis/router/`.

## Finnhub free-tier coverage (verified live with the user's key, 2026-06-04)
All HTTP 200 on the free tier: `/stock/profile2`, `/stock/metric?metric=all`,
`/stock/recommendation`, `/company-news`, `/stock/financials-reported`. Real AAPL metrics returned
(P/E 37.3, net margin 27.2%, gross margin 47.9%, rev/share $30.7, rev growth 12.8% YoY, 52wk
$195-$317, EPS $8.27, beta 1.09). No new key needed. The clean view uses profile2 + metric +
recommendation + company-news; financials-reported is available but raw/heavy (optional, later).

## Dependency graph
```
A1 fundamentals connector (connectors/, httpx)         <- independent unit
        |
A2 company() view  (results.CompanyView -> service.company -> /api/company -> CLI :company)
        |                                   ^ reuses existing symbol_search for name->ticker
        |                                   ^ wired into build_service connectors dict + new TTL
A3 cloud deep-dive (config keys + deps + boundary guard -> router/model_router.py
                    -> service.company_deepdive -> /api/company/{sym}/deepdive -> CLI :deepdive)
                                              ^ reuses A2's deterministic data block; redacts first
```
Build order A1 -> A2 -> A3 (each a complete vertical path, testable before the next).

## Vertical slices

### A1 - Fundamentals connector
- **Files:** `jarvis/connectors/fundamentals.py` (+ `tests/test_connectors_fundamentals.py`).
- **What:** `FundamentalsConnector(Connector)`, `name="fundamentals"`, description for the router.
  `fetch(query)` resolves the symbol like markets.py (regex / first named ticker), then calls
  profile2 + metric + recommendation + company-news and emits one `Item` per facet (profile,
  financials, recommendation, top-N news), each with structured `extra`. Outbound httpx only here.
  Empty key -> `[]` items (never invents). Each endpoint guarded: a non-200 / malformed facet is
  skipped, never raises (partial result survives).
- **Acceptance:**
  - Offline (MockTransport) test: all four facets -> Items with expected `extra` keys/values.
  - Empty key -> `[]`.
  - Per-endpoint non-200 degrades to a partial result (metric 500 still yields profile/news).
  - `name`/`description` set; description mentions fundamentals/financials so the router can pick it.
- **Verify:** `pytest tests/test_connectors_fundamentals.py`.

### A2 - Company view (connector -> service -> API -> CLI)
- **Files:** `jarvis/results.py` (+`CompanyView`), `jarvis/service.py` (`company()`),
  `jarvis/cli.py` (`build_service` wiring + `:company`), `jarvis/api/app.py`
  (`GET /api/company/{symbol}`), `jarvis/config.py` (`cache_ttl_fundamentals`), `.env.example`.
  Tests: `tests/test_service_company.py`, extend `tests/test_api.py`.
- **What:** `CompanyView` (symbol, name, profile fields, key metrics, recommendation summary, recent
  news list, sources, `note` for the no-data/no-key case). `service.company(symbol_or_name)`:
  optionally resolve a name via existing `symbol_search`, fetch via the `fundamentals` connector
  (wrapped in `CachingConnector` with `cache_ttl_fundamentals`), assemble deterministically, emit one
  signal (metadata: symbol). Wire the connector into `_build_knowledge` connectors dict. Thin route
  returns `to_jsonable(service.company(...))`. CLI `:company <symbol|name>` renders it.
- **Acceptance:**
  - Offline test with a fake connector -> populated `CompanyView`; deterministic (no LLM touched).
  - No key / no data -> a `CompanyView` with a clear `note`, never raises.
  - API test: `GET /api/company/AAPL` returns the JSON shape; redacted errors preserved.
  - One signal emitted per call.
- **Verify:** `pytest tests/test_service_company.py tests/test_api.py`; manual `:company AAPL`.

### A3 - Cloud deep-dive (Tier-2 Model Router, opt-in)
- **Files:** `jarvis/config.py` (`anthropic_api_key`, `cloud_model`), `pyproject.toml` (+`anthropic`),
  `tests/test_boundaries.py` (approve `anthropic`; add `router/`-only guard + its regex-pin test),
  `jarvis/router/__init__.py`, `jarvis/router/model_router.py`, `jarvis/service.py`
  (`company_deepdive()`), `jarvis/cli.py` (`build_service` injects the router + `:deepdive`),
  `jarvis/api/app.py` (`POST /api/company/{symbol}/deepdive`).
  Tests: `tests/test_model_router.py`, `tests/test_service_deepdive.py`.
- **What:** `ModelRouter` is the ONLY cloud-crossing module. `deepdive(data_block, instruction)`:
  `redact()` the block (defense in depth), lazy-`import anthropic`, call `cloud_model`, return text.
  No key -> raise `CloudUnavailable` (clean). `service.company_deepdive(symbol)` reuses A2's
  deterministic `CompanyView`, renders it to a text block, sends it through the router, returns the
  report; no key/router -> returns a graceful "deep dive disabled (set ANTHROPIC_API_KEY)" message,
  never raises. One signal (metadata: `{"escalated": true, "symbol": ...}`). Config default
  `cloud_model="claude-sonnet-4-6"` (override `JARVIS_CLOUD_MODEL`; opus possible).
- **Acceptance:**
  - `pytest tests/test_boundaries.py` green WITH `anthropic` added; new guard fails if `anthropic`
    is imported outside `router/`.
  - Model-router test with a fake anthropic client: returns text; **redaction applied before send**
    (plant a secret in the block, assert the captured request is scrubbed).
  - No-key path: `company_deepdive` returns the disabled message, never raises.
  - API route returns the report JSON.
- **Verify:** `pytest tests/test_model_router.py tests/test_service_deepdive.py tests/test_boundaries.py`.

## Checkpoint (end of Phase A, before /ship)
1. Full suite green: `python -m pytest` (offline; no live network in unit tests).
2. `python -m jarvis selftest` still PASS.
3. Manual smoke: `:company AAPL`, `GET /api/company/AAPL`; `:deepdive AAPL` (live cloud, only if the
   user wants to spend tokens).
4. **Check in with the user; they manually test before I commit (/ship).**

## Risks / notes
- Anthropic SDK pulls httpx transitively, but the source import is `anthropic` (not `httpx`), so the
  httpx-only-under-connectors guard is not violated; the new `anthropic`-only-under-router guard makes
  the cloud seam structural.
- Deep dive sends PUBLIC company data only, redacted; the API result carries an escalation flag (UI
  labeling lands with the Phase D navbar).
- financials-reported (absolute revenue/profit) deferred to keep A2's view clean.
