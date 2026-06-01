# Spec: Jarvis — Phase 1 (Knowledge / Retrieval)

> Per-phase implementation spec for the **active** phase. Phase 0 (Foundation) is shipped; its spec
> lives in git history. Design source-of-truth: `CLAUDE.md` (invariants) and
> `docs/Jarvis_Core_Spec.md`. Phase 0 learnings + deferred decisions: `docs/DECISIONS.md`.

## Objective

The first genuinely useful Jarvis: **reactive, grounded, sourced Q&A over live public data.** I ask
about **markets**, **AI / business news**, or **YC / Hacker News**, and Jarvis fetches current public
data and returns a summarized answer **built only from that data, with citations** — never invented
from model memory. If a source returns nothing, it says so.

The compute split is the whole point (CLAUDE.md deterministic-first): the **local LLM only
understands, routes, and summarizes**; **all fetching, parsing, and numeric work is deterministic
code**. The model decides *which* connector(s) apply and *phrases* the result; the connectors produce
*the facts*.

**Who it's for:** the single user (dbhatt24), at the CLI. Reactive only (no proactivity yet).

### Assumptions (correct me before I build)
1. **HN connector first (keyless).** The Algolia HN Search API needs no key, so it is the first
   full vertical slice — it proves interface → connector → cache → route → summarize → CLI before any
   API-key setup exists. Markets and News follow against the same interface.
2. **Markets = Finnhub** (free tier ~60 req/min), **News = GNews** (real-time free tier) — locked.
   Both need keys (placeholders go in `.env`); HN is keyless. Alpha Vantage / NewsAPI are dropped.
3. **"Movers" = a deterministic ranking** of percent-change across a small **configurable watchlist**
   (Finnhub quotes), not a paid "top movers" feed. (Alpha Vantage `TOP_GAINERS_LOSERS` is the alt.)
4. **Default free-text routes through the knowledge pipeline.** When the router finds **no** relevant
   connector, it falls back to Phase 0 plain chat (clearly the model's own knowledge), so general
   questions still work. Grounding is strict **only on the connector path**.
5. **Fetched data is summarized and returned, NOT stored** into the vector store / long-term memory
   (that is Phase 2+). The Phase 0 `:note`/`:recall` features remain unchanged.
6. **httpx** is the HTTP client (already present transitively; promoted to a declared dependency).
7. **Cache hits are shown** with a small `(cached)` marker so the DoD repeat is observable.

## Tech Stack

| Concern | Choice | Why |
|---|---|---|
| HTTP | `httpx` (sync, per-request timeout) | Already transitively present; declare it directly |
| Markets | Finnhub REST (key) — alt: Alpha Vantage | 60/min free; simple `/quote`; verify at build |
| News | GNews REST (key) — alt: NewsAPI | Real-time free tier; NewsAPI free delays 24h + localhost-only |
| HN / YC | Algolia HN Search REST (**keyless**) | No key, stable, ideal first slice |
| Routing + summarizing | Ollama local LLM (Phase 0 `LLMClient`) | Tier-1 conductor; `format="json"` for routing |
| Cache | `Cache` interface, **SQLite** impl (TTL) | Persistent, rate-limit-friendly; **Redis deferred** |
| Config / secrets | `config.py` + `.env` (git-ignored) | API keys via env only, never committed |
| Tests | `pytest` (+ `httpx.MockTransport`) | Offline connector tests via mocked HTTP |
| Lint/format | `ruff` | Unchanged |

**Approved runtime deps (updated):** `python-dotenv`, `ollama`, `chromadb`, **`httpx`**.
No Redis, no web framework, no agent framework. Introduce nothing else without sign-off.

## Commands

```bash
# One-time: add API keys to .env (git-ignored). HN needs none.
#   JARVIS_FINNHUB_API_KEY=...        (markets; or JARVIS_ALPHAVANTAGE_API_KEY)
#   JARVIS_GNEWS_API_KEY=...          (news;    or JARVIS_NEWSAPI_KEY)

python -m jarvis                      # CLI: ask a question, get a grounded sourced answer
python -m jarvis selftest             # DoD self-test (HN live always; markets/news skip without keys)

pytest -q                             # unit tests, fully offline (HTTP + LLM mocked)
pytest -q -m integration              # live: HN always; markets/news only if keys present
ruff check . ; ruff format --check .
```

## Project Structure

```
jarvis/
  connectors/
    __init__.py
    base.py          # Connector (ABC) + Source, Item, ConnectorResult value objects
    hn.py            # HackerNewsConnector  (Algolia HN Search, keyless)   <- slice 1
    markets.py       # MarketsConnector     (Finnhub / Alpha Vantage)      <- slice 2
    news.py          # NewsConnector        (GNews / NewsAPI)              <- slice 3
    caching.py       # CachingConnector     (decorator: wraps any Connector + Cache + TTL)
  cache/
    __init__.py
    base.py          # Cache (ABC): get(key)->str|None (fresh only), set(key, value, ttl)
    sqlite_cache.py  # SQLiteCache (the ONLY new place raw SQL lives)
  knowledge/
    __init__.py
    router.py        # Router: question -> [connector names]  (LLM, format="json")
    answerer.py      # Answerer: (question, results) -> grounded, cited answer  (LLM)
    pipeline.py      # Knowledge: route -> deterministic fetch -> answer
  llm/client.py      # extend: generate(prompt, *, format=None)  (backward compatible)
  config.py          # add: API keys, per-connector TTLs, market watchlist
  cli.py             # default free-text -> Knowledge; fallback to chat; keep :note/:notes/:recall
tests/
  test_connectors_hn.py / _markets.py / _news.py   # normalization via httpx.MockTransport
  test_caching_connector.py   test_sqlite_cache.py
  test_router.py   test_answerer.py   test_pipeline.py
  test_boundaries.py          # extended (see Boundaries)
  (Phase 0 tests remain)
```

Connectors are **independent**: a connector imports only `connectors/base.py` and stdlib/httpx —
never another connector. Adding a 4th source is a new file + one registration line.

## Code Style

The Connector seam mirrors the Phase 0 store seams: an interface + value objects; backend/HTTP code
lives only in the implementation. The summarizer is the only place model prose is produced; it is
fed **only** deterministic data.

```python
# connectors/base.py — the seam. Normalized so every connector looks the same to router/answerer.
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass(frozen=True)
class Source:
    name: str                 # "Hacker News (Algolia)", "Finnhub", "GNews"
    url: str | None = None

@dataclass(frozen=True)
class Item:
    title: str
    detail: str               # one-line human-readable fact (e.g. "NVDA +2.3% to $X")
    url: str | None = None
    extra: dict | None = None  # connector-specific structured fields (e.g. {"change_pct": 2.3})

@dataclass(frozen=True)
class ConnectorResult:
    source: Source
    items: list[Item]
    query: str

class Connector(ABC):
    name: str                 # stable id used by the router: "markets" | "news" | "hn"
    description: str          # what it covers; the router shows this to the LLM to decide relevance

    @abstractmethod
    def fetch(self, query: str) -> ConnectorResult: ...
```

```python
# Grounding is a hard rule. The answerer prompt is, in spirit:
#   "Answer ONLY from the DATA below. Cite sources by name/url. If the data is empty or does not
#    address the question, say you could not find current information. Do NOT use prior knowledge."
# Deterministic code builds the DATA block (titles, details, sources); the LLM only phrases it.
```

Conventions (carry Phase 0 forward): `snake_case`/`PascalCase`, type hints, frozen dataclasses for
value objects, `abc.ABC`/`Protocol` seams, one config location, conventional commits, ruff clean.
**Secrets:** API keys are read from `config`/env only; never logged, never placed in cache keys,
never included in error text or printed URLs (redact). Per `security-and-hardening`.

## Testing Strategy

- **Connectors (unit, offline):** inject an `httpx.Client` backed by `httpx.MockTransport` returning a
  recorded JSON fixture; assert normalization to `Item`s (titles, `detail`, urls, numeric `extra`
  like `change_pct`). No live network.
- **Cache (unit):** temp SQLite; `set` then `get` returns the value while fresh and `None` after TTL
  expiry; `CachingConnector` with a call-counting fake inner asserts a second fetch within TTL does
  **not** hit the inner (cache hit) and a fetch after expiry does.
- **Router (unit):** fake `LLMClient` returning canned JSON; asserts correct names parsed, unknown
  names filtered, empty/garbage → `[]`.
- **Answerer (unit):** fake `LLMClient`; asserts the prompt contains the data + source citations and
  the grounding instruction, and that empty results steer to the "couldn't find" path.
- **Pipeline (unit):** fake router + fake connectors + fake answerer; asserts route→fetch→answer
  wiring and the cache-hit-on-repeat behavior end to end, offline.
- **Integration (`-m integration`):** HN connector hits the **real** Algolia API (keyless) and returns
  items; markets/news integration **skip** when their key env vars are absent. The `selftest` runs the
  HN path live and prints PASS.
- **Coverage intent:** every deterministic path (connectors' normalization, cache, router parsing,
  answerer assembly, pipeline) is unit-tested offline. The model and the network are the only faked
  boundaries.

## Boundaries

- **Always:**
  - Keep the LLM to **route + summarize**; all fetch/parse/numeric work is deterministic code.
  - Summaries are built **only** from fetched data and **cite sources**; empty result → say so.
  - Connectors are independent; program against the `Connector` / `Cache` interfaces.
  - Outbound HTTP happens **only inside `connectors/`** (the trust boundary — only Collectors cross
    out, to public APIs over HTTPS).
  - API keys via `config`/`.env` only; redact from logs/errors; cache before re-hitting an API.
  - `pytest` + `ruff check`/`format --check` before each commit; conventional commits; commit per slice.
- **Ask First:**
  - Adding any dependency beyond {python-dotenv, ollama, chromadb, httpx} (+ pytest, ruff).
  - Changing the `Connector`/`Cache`/`LLMClient` interface signatures.
  - The market/news API provider choice (key-dependent — see Open Questions).
- **Never:**
  - Store fetched data into the vector store / long-term memory; build Phase 2+ (signal capture,
    reflection, user model, proactivity), voice, UI, finance, or cloud/Model Router.
  - Invent or supplement data from model memory on the connector path; commit API keys; log secrets.
  - Pull in Redis or a framework; let one connector import another.

## Success Criteria (Definition of Done — testable)

1. `python -m jarvis`, ask **"what's new on HN about AI"** (or similar) → a grounded, **source-cited**
   summary assembled from **live** Algolia HN data. (Keyless — always demonstrable.)
2. Ask **"what moved in the market today"** → a sourced summary from live Finnhub quotes with
   deterministic percent-change/ranking. (Requires a market key.)
3. Ask **"latest in AI / LLMs"** → a sourced summary from live GNews headlines. (Requires a news key.)
4. **Cache hit on immediate repeat:** asking the same question again returns without a second API call,
   shown with a `(cached)` marker (and asserted in tests via call-count).
5. **Honest empty:** a query a connector can't answer returns "couldn't find current information" —
   **not** a model-memory answer.
6. **Static guards hold:** `httpx` imported only under `connectors/`; raw SQL only in `sqlite_store.py`
   and `cache/sqlite_cache.py`; no connector imports another; declared runtime deps ⊆ the approved
   set. (Each a grep-able test.)
7. `pytest -q` passes fully **offline**; `pytest -q -m integration` passes the HN path live;
   `selftest` prints PASS.

## Decisions (resolved with the user — locked for Phase 1)

1. **Markets = Finnhub** — `/quote` per symbol; key `JARVIS_FINNHUB_API_KEY` (placeholder in `.env`).
2. **News = GNews** — real-time search/headlines; key `JARVIS_GNEWS_API_KEY` (placeholder in `.env`).
3. **"Movers" = deterministic %-change ranking over a configurable watchlist** (Finnhub quotes),
   default `AAPL,MSFT,NVDA,GOOGL,AMZN,META,TSLA` (`JARVIS_MARKET_WATCHLIST`).
4. **No-connector-match → labeled Phase 0 plain chat** (clearly the model's own knowledge), so general
   questions still work; grounding stays strict on the connector path.
5. **`SPEC.md` is the Phase 1 spec** (Phase 0 spec remains in git history at the shipped tip).
6. **Mulch dropped** — not used; Phase 0/1 decisions live in `docs/DECISIONS.md`.
7. **API keys:** `.env` placeholders (`JARVIS_FINNHUB_API_KEY=`, `JARVIS_GNEWS_API_KEY=`) created during
   the build for the user to fill; `.env` is git-ignored; keys never logged or committed.

## Build-time verifications (source-driven-development, at the start of each slice)

Per CLAUDE.md / your instruction — verify against CURRENT official docs before coding, not now:
- **HN (slice 1):** Algolia HN Search base URL, `search` vs `search_by_date`, `tags` (story/front_page),
  and hit fields (`title`, `url`, `points`, `num_comments`, `objectID`, `created_at`).
- **Markets (slice 2):** Finnhub (or AV) current quote/movers endpoint, auth (token param vs header),
  response fields, and the live free-tier rate limit.
- **News (slice 3):** GNews (or NewsAPI) current search/headlines endpoint, auth, fields, and the
  real free-tier limits/caveats (the NewsAPI 24h-delay/localhost restriction in particular).
- **Router:** confirm `ollama` `generate(..., format="json")` behavior on the installed version.

## Build Order (vertical slices → one commit each)

1. **Slice 1 — HN end-to-end (keyless):** `connectors/base` + `hn` + `cache/base`+`sqlite_cache` +
   `caching` + `llm` `format=` + `knowledge/router`+`answerer`+`pipeline` + CLI wiring. Prove the
   full route→fetch→summarize→cite path on a real keyless source. Commit:
   `feat(knowledge): HN connector with routing, grounded summary, and TTL cache`.
2. **Slice 2 — Markets:** `connectors/markets` against the same interface + config key/watchlist +
   tests. Commit: `feat(connectors): markets connector (Finnhub) with deterministic movers`.
3. **Slice 3 — News:** `connectors/news` + config key + tests. Commit:
   `feat(connectors): news connector (GNews)`.
4. **Slice 4 — Harden:** routing robustness (multi-connector, none-match), cache TTL tuning, the
   `selftest` + boundary guards. Commit: `test(knowledge): Phase 1 DoD self-test + boundary guards`.

Then `/test` → `/review` → `/code-simplify` → `/ship` per CLAUDE.md.
