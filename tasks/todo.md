# Phase 1 — TODO

Tracking list for `/build`. One vertical slice per commit; check sub-items as they pass. Full detail
in `tasks/plan.md`. Deterministic-first: LLM routes + summarizes only; connectors fetch.

---

## [x] Slice 1a — plumbing  ·  `feat(knowledge): Phase 1 plumbing (seams, cache, config, LLM format)`
- [x] `pyproject` += `httpx`; `config` += finnhub/gnews keys, watchlist, TTLs; `.env` placeholders + `.env.example`
- [x] `llm/client.py` — `generate(prompt, *, format=None)` (backward compatible)
- [x] `cache/base.py` `Cache` ABC + `cache/sqlite_cache.py` `SQLiteCache` (TTL, WAL; 2nd raw-SQL module)
- [x] `connectors/base.py` `Connector` + `Source`/`Item`/`ConnectorResult` + JSON (de)serialize
- [x] `connectors/caching.py` `CachingConnector` (cache hit skips inner; `last_was_cache_hit`)
- [x] boundary tests updated: SQL allowed in `sqlite_cache.py`; approved deps += httpx
- [x] Verify: offline suite 60 passed; ruff check + format clean

## [x] Slice 1b — HN behavior  ·  `feat(knowledge): HN connector with routing, grounded summary, and TTL cache`
- [x] (source-driven) verified Algolia HN Search API live (endpoint, tags=story, hit fields)
- [x] `connectors/hn.py` `HackerNewsConnector` (injected `httpx.Client`, normalize -> Items)
- [x] `knowledge/router.py` (JSON **schema** + think=False; plain format="json" made qwen3 collapse to {})
- [x] `knowledge/answerer.py` (grounded + cited; empty -> "could not find", never memory)
- [x] `knowledge/pipeline.py` `Knowledge.ask` (None when no connector; failing source contained; cached flag)
- [x] `cli.py` — free-text -> Knowledge; None -> labeled chat; keep :note/:notes/:recall; `(cached)` marker
- [x] Verify: 81 offline green; live router + grounded cited HN answer + cache-hit (pipeline-proven); integration selftest green; ruff clean
  - note: piped-CLI `(cached)` demo is skewed by a Windows PowerShell stdin-BOM artifact; real interactive use caches correctly

### ▸ Checkpoint: HN proven — grounded sourced live answer + cache hit; review before keyed connectors

## [x] Slice 2 — Markets (Finnhub)  ·  `feat(connectors): markets connector (Finnhub) with deterministic movers`
- [x] (source-driven) verified Finnhub `/quote` live (token param; c/d/dp/h/l/o/pc; c==0 = unknown symbol)
- [x] `connectors/markets.py` — watchlist (+ named tickers) quotes -> movers ranked by |dp|; no-key -> empty
- [x] registered in pipeline (CachingConnector, markets TTL)
- [x] Verify: offline units (MockTransport rank + no-key + watchlist); live router->markets + grounded movers; ruff clean

## [x] Slice 3 — News (GNews)  ·  `feat(connectors): news connector (GNews)`
- [x] (source-driven) verified GNews `/search` from docs (apikey param; title/description/url/publishedAt/source.name)
- [x] `connectors/news.py` — query -> headlines -> Items; no-key / non-200 -> empty (never invents)
- [x] registered in pipeline (CachingConnector, news TTL)
- [x] Verify: offline units (fixture + no-key + 403); live router->news + graceful 403; ruff clean
  - [ ] PENDING GNews activation: live news answers (key valid; account needs email verification at gnews.io)

### ▸ Checkpoint: all three connectors live — review before hardening

## [ ] Slice 4 — Harden + DoD self-test + boundary guards  ·  `test(knowledge): Phase 1 DoD self-test + boundary guards`
- [ ] routing robustness (multi-connector, none-match labeled chat, malformed -> [])
- [ ] `selftest` — live HN route->fetch->summarize PASS; markets/news skip w/o keys
- [ ] `test_boundaries.py` — httpx only in connectors/; SQL only in sqlite_store.py + cache/sqlite_cache.py; no connector imports another; deps ⊆ {python-dotenv, ollama, chromadb, httpx}
- [ ] per-connector cache TTLs tuned
- [ ] Verify: `pytest -q` offline green; `-m integration` HN green; `selftest` PASS; ruff clean

### ▸ Checkpoint: Phase 1 DoD met → `/test` → `/review` → `/code-simplify` → `/ship`
