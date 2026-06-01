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

## [ ] Slice 1b — HN behavior  ·  `feat(knowledge): HN connector with routing, grounded summary, and TTL cache`
- [ ] (source-driven) verify Algolia HN Search API (endpoint, tags, hit fields)
- [ ] `connectors/hn.py` `HackerNewsConnector` (injected `httpx.Client`, normalize -> Items)
- [ ] `knowledge/router.py` (format=json -> [names], filter unknown, []-on-none)
- [ ] `knowledge/answerer.py` (grounded + cited; empty -> couldn't find)
- [ ] `knowledge/pipeline.py` `Knowledge.ask` (None when no connector)
- [ ] `cli.py` — free-text -> Knowledge; None -> labeled chat; keep :note/:notes/:recall; `(cached)` marker
- [ ] Verify: offline units (MockTransport, fake LLM); `-m integration` HN live; manual HN answer + `(cached)`; ruff clean

### ▸ Checkpoint: HN proven — grounded sourced live answer + cache hit; review before keyed connectors

## [ ] Slice 2 — Markets (Finnhub)  ·  `feat(connectors): markets connector (Finnhub) with deterministic movers`
- [ ] (source-driven) verify Finnhub `/quote` (token param; c/d/dp/h/l/o/pc) + rate limit
- [ ] `connectors/markets.py` — watchlist quotes -> deterministic %-change movers -> Items; no-key -> empty + note
- [ ] register in pipeline (CachingConnector, markets TTL)
- [ ] Verify: unit (fixture %-change/rank + no-key); integration skips w/o key; manual "what moved today"; ruff clean

## [ ] Slice 3 — News (GNews)  ·  `feat(connectors): news connector (GNews)`
- [ ] (source-driven) verify GNews `/search` (apikey param; title/description/url/source/publishedAt) + limit
- [ ] `connectors/news.py` — query -> headlines -> Items; no-key -> empty + note
- [ ] register in pipeline (CachingConnector, news TTL)
- [ ] Verify: unit (fixture + no-key); integration skips w/o key; manual "latest in AI/LLMs"; ruff clean

### ▸ Checkpoint: all three connectors live — review before hardening

## [ ] Slice 4 — Harden + DoD self-test + boundary guards  ·  `test(knowledge): Phase 1 DoD self-test + boundary guards`
- [ ] routing robustness (multi-connector, none-match labeled chat, malformed -> [])
- [ ] `selftest` — live HN route->fetch->summarize PASS; markets/news skip w/o keys
- [ ] `test_boundaries.py` — httpx only in connectors/; SQL only in sqlite_store.py + cache/sqlite_cache.py; no connector imports another; deps ⊆ {python-dotenv, ollama, chromadb, httpx}
- [ ] per-connector cache TTLs tuned
- [ ] Verify: `pytest -q` offline green; `-m integration` HN green; `selftest` PASS; ruff clean

### ▸ Checkpoint: Phase 1 DoD met → `/test` → `/review` → `/code-simplify` → `/ship`
