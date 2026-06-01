# Implementation Plan: Jarvis — Phase 1 (Knowledge / Retrieval)

> Derived from SPEC.md (validated; decisions locked). Reactive, grounded, sourced Q&A over live
> public data. Deterministic-first: the LLM only routes + summarizes; connectors fetch
> deterministically. One vertical slice per commit; a slice is done only when its acceptance +
> verification pass. Phase 0 plan is in git history.

## Overview

Add a pluggable `Connector` seam and three public-data connectors (HN keyless, Finnhub markets,
GNews news), a SQLite TTL cache applied via a `CachingConnector` decorator, and an LLM
route -> fetch -> summarize pipeline that answers only from fetched data with citations. HN is built
first (keyless) so the whole path is proven before any API keys exist.

## Architecture Decisions (locked in SPEC.md)

- Connectors behind a `Connector` interface; outbound HTTP lives ONLY in `connectors/` (trust
  boundary, enforced by a boundary test). Connectors are independent (no cross-imports).
- Cache behind a `Cache` interface, SQLite impl, applied as a `CachingConnector` decorator (cache
  logic written once, not per connector). Redis deferred.
- LLM = Tier-1 conductor: `Router` (format="json") picks connectors; `Answerer` summarizes ONLY the
  fetched data with citations; empty -> "couldn't find current information", never model memory.
- Markets = Finnhub (movers = deterministic %-change over a configurable watchlist); News = GNews.
- No-connector-match -> labeled Phase 0 plain chat (general Q&A still works).
- API keys via `.env` placeholders (created for the user to fill); never committed/logged.
- New runtime dep: `httpx` (approved set += httpx). No Redis, no framework.

## Dependency Graph

```
Slice 1  HN end-to-end (keyless)  [foundational]
  foundation: pyproject(+httpx) + config(keys/TTL/watchlist) + .env placeholders + LLMClient `format=`
        |
  cache/base + cache/sqlite_cache          connectors/base (Connector + Source/Item/ConnectorResult)
        \________________________  ________________________/
                                 \/
                  connectors/caching (CachingConnector)   connectors/hn (HackerNewsConnector)
                                 |
       knowledge/router (format=json) -> deterministic fetch -> knowledge/answerer -> knowledge/pipeline
                                 |
       cli: free-text -> Knowledge; no-match -> labeled chat; keep :note/:notes/:recall; (cached) marker
        v
Slice 2  Markets (Finnhub)  -> connectors/markets (watchlist quotes -> %-change movers) + register
        v
Slice 3  News (GNews)       -> connectors/news + register
        v
Slice 4  Harden            -> selftest (HN live) + boundary guards + routing robustness + cache tuning
```

Slice 1 establishes the seams + pipeline. Slices 2 and 3 are independent connectors against the same
interface, but both edit the pipeline's connector registry, so run 2 then 3. Slice 4 depends on all.

> **Sizing note:** Slice 1 is **Large** (the foundational slice: seams + cache + HN + pipeline + CLI,
> ~10 source files). It is buildable as one green commit, but for reviewability it can be split into
> **1a (plumbing: deps/config/.env/LLMClient/Cache/CachingConnector/Connector base)** and
> **1b (behavior: HN connector + router/answerer/pipeline + CLI)**. Recommend 1a/1b; confirm in review.

## Task List

### Slice 1 — HN end-to-end (keyless)

**Source-driven first:** verify the Algolia HN Search API against current docs (base URL,
`search` vs `search_by_date`, `tags`=story/front_page, hit fields `title`/`url`/`points`/
`num_comments`/`objectID`/`created_at`).

**Acceptance criteria:**
- [ ] `pyproject.toml` declares `httpx`; `pip install -e ".[dev]"` succeeds.
- [ ] `config.py` adds `finnhub_api_key`, `gnews_api_key` (env, may be empty), `market_watchlist`
  (default `AAPL,MSFT,NVDA,GOOGL,AMZN,META,TSLA`), per-connector cache TTLs. `.env` created with empty
  key placeholders; `.env.example` documents them.
- [ ] `llm/client.py`: `generate(prompt, *, format=None)` forwards `format` to ollama; Phase 0 callers
  unaffected (default None).
- [ ] `cache/base.py` `Cache` ABC (`get(key)->str|None` returns fresh-only, `set(key, value, ttl)`);
  `cache/sqlite_cache.py` `SQLiteCache` (table `cache(key PK, value, expires_at)`; the ONLY new raw-SQL
  module).
- [ ] `connectors/base.py`: `Connector` ABC + frozen `Source`/`Item`/`ConnectorResult`.
- [ ] `connectors/hn.py`: `HackerNewsConnector` (name `"hn"`, description) fetches via an injected
  `httpx.Client`, normalizes hits -> `Item`s (title, detail=points/comments, url, extra).
- [ ] `connectors/caching.py`: `CachingConnector(inner, cache, ttl)` — cache hit skips `inner.fetch`.
- [ ] `knowledge/router.py`: `Router(llm, connectors).route(question)->[names]` via `format="json"`;
  filters unknown names; `[]` on none/garbage.
- [ ] `knowledge/answerer.py`: `Answerer(llm).answer(question, results)->str` grounded + cited; empty
  results -> "couldn't find current information".
- [ ] `knowledge/pipeline.py`: `Knowledge.ask(question)->str|None` (None when no connector matched).
- [ ] `cli.py`: free-text -> `Knowledge.ask`; None -> labeled plain-chat fallback; keep
  `:note`/`:notes`/`:recall`; show `(cached)` on cache hits.

**Verification:**
- [ ] Unit (offline): HN normalization via `httpx.MockTransport`; `SQLiteCache` TTL fresh/expired;
  `CachingConnector` call-count (2nd within TTL skips inner); router parse (fake-LLM JSON, unknown
  filtered, garbage->[]); answerer grounding (fake LLM, empty->couldn't-find); pipeline wiring +
  cache-hit. `pytest -q` green with no network/Ollama.
- [ ] Integration: `pytest -q -m integration` -> HN hits real Algolia, returns items.
- [ ] Manual (Ollama up): ask "what's new on HN about AI" -> grounded sourced summary; repeat ->
  `(cached)`.
- [ ] `ruff check .` + `ruff format --check .` clean.

**Files:** `pyproject.toml`, `config.py`, `.env`, `.env.example`, `llm/client.py`,
`cache/{__init__,base,sqlite_cache}.py`, `connectors/{__init__,base,hn,caching}.py`,
`knowledge/{__init__,router,answerer,pipeline}.py`, `cli.py`, `tests/test_sqlite_cache.py`,
`tests/test_connectors_hn.py`, `tests/test_caching_connector.py`, `tests/test_router.py`,
`tests/test_answerer.py`, `tests/test_pipeline.py`, `tests/test_boundaries.py` (update).
**Scope:** L (split 1a/1b recommended).
**Commit:** `feat(knowledge): HN connector with routing, grounded summary, and TTL cache`

### Checkpoint: HN proven
- [ ] Offline suite green, ruff clean; live HN answer is grounded + cited; repeat shows `(cached)`.
- [ ] Review before adding the keyed connectors.

### Slice 2 — Markets (Finnhub)

**Source-driven first:** verify Finnhub `/quote` (auth = `token` query param; fields
`c`=current, `d`=change, `dp`=percent, `h`/`l`/`o`/`pc`) + live free-tier limit.

**Acceptance criteria:**
- [ ] `connectors/markets.py`: `MarketsConnector` (name `"markets"`) — fetch quotes for the watchlist
  (plus any tickers detected in the query), compute %-change deterministically, rank movers ->
  `Item`s (e.g. detail "NVDA +2.3% to $X", extra `{change_pct, price}`); cite Finnhub. Reads
  `config.finnhub_api_key`; **no key -> empty `ConnectorResult` with a clear note** so the answerer
  says it couldn't fetch (never invents).
- [ ] Registered in the pipeline's connector set, wrapped in `CachingConnector` (markets TTL, short).

**Verification:** unit (MockTransport fixture -> %-change math + ranking + no-key path); integration
skips without `JARVIS_FINNHUB_API_KEY`; manual "what moved today" with key. ruff clean.
**Files:** `connectors/markets.py`, pipeline registration, `tests/test_connectors_markets.py`.
**Scope:** M. **Commit:** `feat(connectors): markets connector (Finnhub) with deterministic movers`

### Slice 3 — News (GNews)

**Source-driven first:** verify GNews `/search` (and/or `/top-headlines`) (auth = `apikey`/`token`
param; fields `title`/`description`/`url`/`source`/`publishedAt`) + free-tier limit.

**Acceptance criteria:**
- [ ] `connectors/news.py`: `NewsConnector` (name `"news"`) -> headlines for the query -> `Item`s
  (title, detail = source + published, url); cite GNews; no-key -> empty + note.
- [ ] Registered (CachingConnector, news TTL).

**Verification:** unit (fixture normalization + no-key path); integration skips without
`JARVIS_GNEWS_API_KEY`; manual "latest in AI/LLMs". ruff clean.
**Files:** `connectors/news.py`, pipeline registration, `tests/test_connectors_news.py`.
**Scope:** M. **Commit:** `feat(connectors): news connector (GNews)`

### Checkpoint: all three connectors
- [ ] Offline suite green; each connector demonstrable live (HN always; markets/news with keys).
- [ ] Review before hardening.

### Slice 4 — Harden + DoD self-test + boundary guards

**Acceptance criteria:**
- [ ] Routing robustness: multi-connector selection; none-match -> labeled chat; malformed router
  output -> `[]` gracefully.
- [ ] `selftest`: live HN route->fetch->summarize prints PASS; markets/news steps skip without keys.
- [ ] `tests/test_boundaries.py` extended: `httpx` imported only under `connectors/`; raw SQL only in
  `sqlite_store.py` + `cache/sqlite_cache.py`; no connector imports another connector; declared runtime
  deps ⊆ {python-dotenv, ollama, chromadb, httpx}.
- [ ] Per-connector cache TTLs tuned (markets short; news/HN moderate).

**Verification:** `pytest -q` offline green; `pytest -q -m integration` HN green;
`python -m jarvis selftest` PASS; `ruff check`/`format --check` clean.
**Files:** `knowledge/pipeline.py`, `jarvis/selftest.py`, `tests/test_boundaries.py`,
`tests/test_pipeline.py`.
**Scope:** M. **Commit:** `test(knowledge): Phase 1 DoD self-test + boundary guards`

### Checkpoint: Phase 1 complete
- [ ] All SPEC.md DoD met; `selftest` PASS; offline + HN-integration green; ruff clean.
- [ ] Proceed `/test` -> `/review` -> `/code-simplify` -> `/ship`.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| External API drift (endpoints/auth change) | High likelihood / Med | Source-driven verify at the START of each slice; connectors isolate blast radius to one file |
| Finnhub/GNews need keys / free-tier limits | Med | HN keyless proves the path; graceful no-key (empty + note); cache respects rate limits |
| Router picks wrong/no connector | Med | `format="json"` + validate against known names + none-match labeled-chat fallback; fetch is deterministic |
| Grounding leakage (model adds memory) | Med/High | Strict answerer prompt; tests assert empty -> "couldn't find"; data block built deterministically |
| Secret leakage (keys in logs/errors/cache keys) | Med | Keys only from env; redact from errors; cache key = connector+query, never the key; `.env` git-ignored |
| Windows/SQLite cache file handling | Low | Single-process Phase 1; cache is its own sqlite file; reuse Phase 0 path patterns |

## Open Questions
- None blocking. Exact API endpoints/fields are verified per slice via source-driven-development.

## Parallelization
- Slice 1 must land first (seams + pipeline). Slices 2 and 3 are independent connectors but both touch
  the pipeline registry, so serialize (2 then 3). Slice 4 is a barrier (needs all connectors).
