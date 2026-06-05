# Phase A — TODO (Stocks/company depth + cloud-escalation engine)

Tracking list for `/build`. One vertical slice at a time; full plan in `tasks/plan.md`.
Additive only; `pytest` + `ruff` green before each commit. Commit style: conventional, no em-dashes,
no attribution (reads as user-authored).

## A1 — Fundamentals connector
- [ ] `jarvis/connectors/fundamentals.py` — `FundamentalsConnector`: profile2 + metric + recommendation + company-news -> Items with structured `extra`; httpx only here; empty key -> []; per-endpoint failure degrades to partial, never raises
- [ ] `tests/test_connectors_fundamentals.py` — MockTransport: all facets, empty key, per-endpoint non-200 partial, name/description
- [ ] `pytest tests/test_connectors_fundamentals.py` + `ruff check .` green

## A2 — Company view (connector -> service -> API -> CLI)
- [ ] `jarvis/results.py` — `CompanyView` dataclass (profile + metrics + recommendation + news + sources + note)
- [ ] `jarvis/config.py` — `cache_ttl_fundamentals`
- [ ] `jarvis/service.py` — `company(symbol_or_name)`: name->ticker via symbol_search, fetch via fundamentals connector, deterministic assembly, one signal; no-key/no-data -> CompanyView with note
- [ ] `jarvis/cli.py` — wire `fundamentals` connector into `build_service`; `:company <symbol|name>`
- [ ] `jarvis/api/app.py` — `GET /api/company/{symbol}`
- [ ] `.env.example` — document `JARVIS_CACHE_TTL_FUNDAMENTALS`
- [ ] `tests/test_service_company.py` + extend `tests/test_api.py`
- [ ] `pytest tests/test_service_company.py tests/test_api.py` + `ruff` green; manual `:company AAPL`

## A3 — Cloud deep-dive (Tier-2 Model Router, opt-in)
- [ ] `jarvis/config.py` — `anthropic_api_key`, `cloud_model` (default claude-sonnet-4-6)
- [ ] `pyproject.toml` — add `anthropic` dependency; `pip install -e .[dev]`
- [ ] `tests/test_boundaries.py` — add `anthropic` to approved deps; new guard: `anthropic` only under `router/` (+ regex-pin test)
- [ ] `jarvis/router/__init__.py`, `jarvis/router/model_router.py` — `ModelRouter.deepdive(block, instruction)`: redact -> anthropic -> text; no key -> `CloudUnavailable`
- [ ] `jarvis/service.py` — `company_deepdive(symbol)`: reuse CompanyView block, route, return report; no key -> graceful disabled message; one signal (escalated)
- [ ] `jarvis/cli.py` — inject router in `build_service`; `:deepdive <symbol>`
- [ ] `jarvis/api/app.py` — `POST /api/company/{symbol}/deepdive`
- [ ] `tests/test_model_router.py` (fake client; assert redaction-before-send) + `tests/test_service_deepdive.py` (no-key graceful)
- [ ] `pytest tests/test_model_router.py tests/test_service_deepdive.py tests/test_boundaries.py` green

## Checkpoint (end of Phase A)
- [x] `python -m pytest` full suite green
- [x] `python -m jarvis selftest` PASS
- [x] Live smoke: company("AAPL") returns full profile/metrics/analyst/news
- [x] `/review` done (APPROVE; redact over-redaction fixed + regression-tested)
- [ ] Ship (awaiting user manual test)

## Phase B - News depth (GDELT + GNews)  [BUILT, awaiting ship]
- [x] `jarvis/connectors/gdelt.py` - keyless GDELT DOC 2.0 connector; English filter; 429 -> empty
- [x] `jarvis/config.py` - `cache_ttl_gdelt` (900s)
- [x] `jarvis/cli.py` - wired GdeltConnector into build_service (alongside GNews)
- [x] `.env.example` - documented GDELT (keyless) + TTL
- [x] `tests/test_connectors_gdelt.py` - 10 tests (map/english-filter/429/malformed/params)
- [x] full suite green, ruff clean, selftest PASS
- [x] FIX (found in manual test): conversational questions returned 0 news. Added `jarvis/query.py`
      keyword extractor; NewsConnector falls back to /top-headlines (category=world), GdeltConnector
      to a broad world query, when the question has no specific subject. Live e2e now grounded+cited.
- [x] 461 passed; live `ask("what is going on around the world right now?")` -> real cited answer
- [ ] Ship (awaiting user manual test)

## Phase C/D - Cockpit surfacing of A+B + 3D news globe  [BUILT, awaiting ship]
One cohesive frontend upgrade (decided w/ user: full 3D globe via three.js; weather skipped).
- [x] Backend: `GET /api/news` - `results.NewsItem`, `service.news()` READ-ONLY (no signal), reuses
      GDELT+GNews via `self._fetch`; `tests/test_service_news.py` + `test_api.py` route tests
- [x] Company depth (frontend-only; routes already existed): `CompanyPanel` modal (profile + metric grid
      + analyst + recent news) + confirm-before-spend cloud Deep Dive ("CLOUD-ESCALATED" label, graceful
      disable w/o ANTHROPIC_API_KEY); clickable `StockTile` -> opens it
- [x] Navbar + view switch: `NavBar` (Cockpit|News) in StatusBar; `AppShell hideSide` for full-width News
- [x] 3D world-news globe: `react-globe.gl` (lazy-loaded; main bundle stays ~145KB gz, globe chunk ~524KB
      gz), `NewsGlobe`/`NewsView`, `countryCentroids` (GDELT country -> [lat,lng]); **LOCAL** earth texture
      `public/earth-dark.jpg` (no CDN); auto-rotate off under reduced-motion; honest GDELT-429 empty state
- [x] 468 passed, ruff/tsc/vite-build clean, selftest PASS; five-axis `/review` -> APPROVE (GO)
- [ ] Ship (awaiting user manual test)
