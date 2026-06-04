# Decisions Log (Jarvis)

Lightweight ADR-style log. Phase 0 established the foundation; the items below were surfaced during
the Phase 0 build, review, and ship gate and deliberately deferred. Revisit each in the noted phase.

> The project intends to track this in Mulch (`ml record`), but the `ml`/`mulch` CLI is not installed
> in this environment, so decisions are recorded here for now. Port to Mulch once the CLI is available
> (the `.mulch/` store already exists).

## Deferred decisions (revisit in the noted phase)

### D1 - Vector distance metric: Chroma default L2 vs SPEC 7.1 cosine - RESOLVED (Phase 2 Slice 1b)
`ChromaVectorStore` now takes a `space` arg; the memory collection is created with
`metadata={"hnsw:space": "cosine"}` and `MemoryStore.retrieve` computes relevance as `1 - distance`.
Verified against the installed chromadb. The default (no `space`) still keeps L2 for any other use.

### D2 - Data directory tied to source location (revisit: Phase 2 Heartbeat)
`config._ROOT = Path(__file__).resolve().parent.parent` anchors `data/` to the source tree. Correct
for the editable Phase 0 install; breaks for a packaged/non-editable install or a Heartbeat service
running from a different CWD. Move to a user/OS data dir (e.g. platformdirs or %LOCALAPPDATA%) when
the Heartbeat becomes a real long-lived service.

### D3 - Chroma add vs upsert on duplicate id - RESOLVED (Phase 2 Slice 1b)
`VectorStore` now exposes `upsert` (full write) and `update_metadata` (metadata-only, no re-embed);
`MemoryStore.save` upserts and `retrieve` bumps `last_accessed_at` via `update_metadata`. The Phase 0
`add` remains for genuinely append-only writes. Verified `collection.update` accepts metadata-only.

### D4 - ChromaVectorStore has no close() (revisit: Phase 2 long-lived processes)
`SQLiteStructuredStore.close()` exists; `ChromaVectorStore` holds file handles with no close(),
worked around in selftest via `ignore_cleanup_errors`. Add a close() and call it from `cli.run()`'s
finally when the always-on Heartbeat runs long-lived processes.

### D5 - Enforce loopback Ollama host in code, not just by default (revisit: Phase 2 data capture)
`JARVIS_OLLAMA_HOST` defaults to localhost but is unchecked, so a misconfig could send prompts/notes
to a remote endpoint over plaintext HTTP. The trust boundary currently rests on the default value.
When Phase 2 turns on real private-data capture, warn or refuse on a non-loopback host unless
explicitly overridden (mirror the Chroma telemetry-off enforcement).

### D6 - Dependency pinning and CVE auditing (revisit: before deps grow / first CI)
Runtime floors are loose (`>=`); chromadb pulls a large transitive surface (onnxruntime, grpcio,
uvicorn, kubernetes, OTLP). Add a hash-pinned lockfile and wire `pip-audit` into CI; re-pin to tested
majors (e.g. `chromadb>=1.5,<2`) so a 2.x change cannot silently land.

## Phase 0 conventions established (carry forward)

- Four seams behind interfaces (`LLMClient`, `Embedder`, `StructuredStore`, `VectorStore`); backend
  code lives only in its implementation module. Enforced by `tests/test_boundaries.py` (no raw SQL
  outside sqlite_store.py, no chromadb outside chroma_store.py, declared deps within an approved set).
- Local-first: Chroma telemetry disabled in code; the only network egress is localhost Ollama.
- Offline tests fake the model boundary (FakeLLMClient; a deterministic SHA1 bag-of-words embedder in
  conftest) so similarity assertions are stable; one live integration test gates the real stack and
  skips when Ollama is unreachable.
- Write ordering: embed before saving a note so a backend failure never diverges the two stores.
- Verified library shapes (Phase 0): ollama 0.6.2 `Client.generate(model, prompt).response` and
  `Client.embed(model, input).embeddings`; chromadb 1.5.9 bring-your-own-embeddings via
  PersistentClient + get_or_create_collection (no embedding_function) + explicit embeddings= /
  query_embeddings=.

## Phase 1 review notes (deferred to Phase 2)

### D7 - Markets connector makes N sequential Finnhub calls (revisit: scale/latency)
`MarketsConnector.fetch` calls /quote once per watchlist symbol (~7), sequentially, on a cache miss
(~1-2s first-query latency). Fine for Phase 1 (reactive + cached). Parallelize (threads or async
httpx) or move to a batch quote source when latency or watchlist size grows.

### D8 - Cache key is connector:query only (revisit: when params become user-tunable)
The cache key does not include connector parameters (e.g. the market watchlist), so a mid-session
`JARVIS_MARKET_WATCHLIST` change serves stale results until the TTL expires. Fold relevant params
into the key when they become runtime-tunable.

### D9 - Grounding is prompt-enforced; empty conflates error with no-data (revisit: Phase 2 surfacing)
The answerer instructs the LLM to use only the provided data and to say "could not find" when empty,
but cannot guarantee no leakage (standard RAG). Empty results also conflate "no key / fetch error"
with "genuinely no data". When Phase 2 surfaces suggestions/briefings, distinguish fetch-failure from
empty and consider a verification pass.

### D10 - CachingConnector.last_was_cache_hit is instance state (revisit: Phase 2 Heartbeat)
The cache-hit flag is single-threaded instance state. Revisit for the multi-process always-on
Heartbeat (a per-call return value or thread-local) so the `(cached)` signal stays correct.

## Phase 2 conventions established (carry forward)

- Storage split is real: relational facts (`Goal`, `Note`, `SignalEvent`) go through
  `StructuredStore`/SQLite; semantic memory (`MemoryRecord`) lives in the cosine vector store with its
  scalar fields in Chroma metadata (lists/dicts JSON-encoded, since Chroma metadata is flat scalars).
- Deterministic-first held end-to-end: §7.1 retrieval, date math, goal logic, and the briefing DATA
  block are all code; the LLM only phrases. The briefing feeds the model ONLY the assembled block
  (asserted byte-for-byte) and runs on local Ollama, so no private data crosses outward.
- Trust boundary extended for the first private-data integration: the 3 Google libs are confined to
  `jarvis/calendar/` (boundary-guarded with `google\w*` so underscore packages are caught too);
  `credentials.json` + `token.json` live in git-ignored `./data/`; scope is `calendar.readonly`.
- Front-ends share one core via the CLI today; signals are captured per turn for every modality.
- Migrations derive the target id deterministically from the source (`note-<id>`) so a partial-failure
  retry upserts instead of duplicating - the pattern for any future store migration.
- Verified library shapes (Phase 2): google-auth-oauthlib `InstalledAppFlow.from_client_secrets_file`
  + `run_local_server(port=0)`; `Credentials.from_authorized_user_file` + `.valid/.expired/
  .refresh_token/.refresh(Request())/.to_json()`; googleapiclient `build("calendar","v3",
  credentials=..., cache_discovery=False)`, `events().list(calendarId, timeMin, timeMax,
  singleEvents=True, orderBy="startTime").execute()`; Chroma `collection.update(ids, metadatas=...)`
  updates metadata only.

## Phase 2 review/ship notes (deferred)

### D11 - Recency self-decay on repeat recall (revisit: Phase 5 ranking)
`retrieve` bumps `last_accessed_at = now` for every returned record, and recency is measured from
`last_accessed`, so a frequently recalled memory keeps resetting to maximum recency and can crowd out
genuinely recent-but-unread memories as the corpus grows. Per §7.1 as written; flag for Phase 5
ranking so it isn't inherited as a surprise.

### D12 - Candidate-pool truncation gates on relevance (revisit: Phase 5 / large corpus)
`retrieve` fetches the top-`memory_candidate_pool` (20) by vector similarity, THEN re-ranks by
recency/importance/relevance. A high-importance but semantically-distant memory ranked #21 never
enters the pool, so importance/recency cannot rescue it. Intentional (relevance gates the pool) and
fine while the corpus is small; revisit when memory grows (e.g. union a top-importance pool).

### D13 - `_redact` does not cover OAuth/Bearer token formats (revisit: if tokens get logged)
`_redact` matches only `token=`/`apikey=` URL forms. Verified that today's google-auth `RefreshError`
string does NOT embed the token, so there is no current leak. If a future path prints a raw
token-bearing string, broaden the pattern to `access_token`/`refresh_token`/`Bearer`/`ya29.`/`1//`.

### D14 - Boundary guards are text-based lints, not enforcement (revisit: hardening / CI)
The import guards catch honest mistakes but are bypassable (`importlib`, re-export) and only cover
`httpx`/`google`; they don't guard other egress transports (`socket`, `urllib`, `requests`). Highest-
leverage addition: assert no `socket`/`urllib.request`/`requests` import outside `connectors/`, since
the invariant is "any outbound transport = trust boundary", not just httpx.

### D15 - `day_bounds` uses the local machine tz, not the Google calendar tz (revisit: Heartbeat/tz)
"Today" is derived from the host's local timezone; if the user's Google calendar tz differs, the
window can be off by the offset (an edge-of-day event slips out). Fine for a single-user local
foundation; revisit if the Heartbeat box runs in a different tz than the user.

### D16 - Dependency floors still loose; add a lockfile (extends D6, revisit: first CI)
The 3 Google floors (`>=2.0`/`>=1.0`/`>=0.2`) permit old transitive `google-auth`/`cryptography` on a
fresh resolve, though the installed set is current. Raise floors to validated minimums and add a
lockfile when CI lands (folds into D6).

## Phase 3 conventions established (carry forward)

- One facade, thin front-ends: `JarvisService` (jarvis/service.py) is the single application-service
  layer; CLI, GUI, and voice are interchangeable front doors that call it and render only - no business
  logic in `ui/` or `voice/`. `build_service(source)` is the shared composition; `source` ("cli"|"gui"|
  "voice") is stamped into every signal so Phase 5's history covers all modalities.
- Signal capture is centralized in the facade: each capability emits exactly one SignalEvent (incl. on
  failure, via the `_signal` contextmanager) and payloads stay metadata-only (source/path/count/id/error
  TYPE) - never query text, goal text, or transcripts.
- New surfaces sit behind seams, boundary-guarded: Flet only under `ui/`; the local voice libs
  (`faster_whisper`/`sounddevice`/`piper`) only under `voice/`; heavy libs are imported lazily so the
  pure logic (feed/controller, loop) unit-tests without models, audio, or a window.
- Local-only audio: mic audio + transcripts never touch disk or the signal log and have no outbound
  path; STT/TTS make no network call at inference (model weights are a one-time public-weight fetch).
- Front-ends must not crash on a backend failure: the CLI's REPL guard, the GUI controller's error
  card, and the voice loop's per-turn guard all keep the surface alive (and redact via `jarvis/redact.py`).
- Verified library shapes (Phase 3): Flet 0.85 (`ft.run(main)`, `page.add/update`, Card/ListView/
  TextField/Button/Markdown); faster-whisper 1.2 (`WhisperModel(...).transcribe(audio) -> (segments,
  info)`); sounddevice 0.5 (`InputStream`/`rec`/`play`); piper-tts 1.4 (`PiperVoice.load(path)`,
  `synthesize(text) -> AudioChunk(audio_int16_array, sample_rate)`).

## Phase 3 review/ship notes (deferred)

### D17 - Public-data search connectors transmit the query term (revisit: Phase 5 PII)
By design, when the local router selects the news/HN connector the user's question (now also voice
transcripts) is sent verbatim as the search term to GNews/Algolia HN (markets sends only tickers). This
is the sanctioned public-data egress, gated by the local router returning [] for non-public questions -
not a private-data leak. For defense-in-depth in Phase 5, gate connector dispatch on a deterministic
public-data trigger and/or strip PII before `fetch`. Document the one-line exception when ARCHITECTURE.md
lands so "nothing private leaves" stays precise.

### D18 - Boundary guards are import-name lints, not egress control (extends D14)
The httpx/google/flet/voice guards enforce "known libs stay in their lane"; they do not stop a non-httpx
egress (`socket`, `urllib`, `http.client`, `requests`). No such egress exists today. Highest-leverage
add when hardening: assert those transports don't appear outside `connectors/`.

### D19 - Add a lockfile for the now-large dependency surface (extends D6/D16)
Phase 3 added flet + the voice stack (ctranslate2, av/ffmpeg, onnxruntime). Floors allow a future
`pip install` to pull newer (possibly compromised) releases - a reproducibility risk more than a live
CVE for local use. Commit a hash-pinned `requirements.lock`/`uv.lock` when CI lands.

## Phase 4 conventions established (carry forward)

- The absolute rule, made structural: EVERY financial figure is computed by the deterministic engine
  (`finance/engine.py`), which imports NO LLM (a boundary test greps it). The LLM only classifies a
  merchant string, parses a question into a FinanceQuery, and phrases an already-computed figure - the
  Q&A test asserts the answered number equals the engine's output, never a model-invented one.
- Money is `decimal.Decimal` end to end, stored as TEXT (exact), never float/REAL. `finance/money.py`
  is the one place to quantize to cents + format for display; `make_id` quantizes before hashing so
  -12.5 and -12.50 are the same transaction (idempotent across sources).
- Source signs differ and are normalized to ours (negative = outflow): OFX TRNAMT is already negative-
  for-outflow; Plaid `amount` is positive-for-outflow (negated) AND Plaid liability balances (credit/
  loan) are positive-for-debt (negated for net worth). Getting a sign wrong corrupts every figure.
- Trust boundary: CSV/OFX import is fully local; Plaid is the ONE outbound path - lazy-imported,
  token-gated, boundary-confined to `finance/`. Signal log is metadata-only (no amounts, balances, or
  merchant strings - only metric/count/category-enum labels). Two hard Nevers hold structurally:
  no money-movement API is imported anywhere, and phrasing prompts report facts (no advice).
- Verified library shapes (Phase 4): ofxtools `OFXTree().parse(f).convert()` -> statements (trnamt/
  ledgerbal already Decimal, requires a valid SIGNON block); plaid-python 39 Configuration/PlaidApi +
  transactions_sync (added/next_cursor/has_more) + accounts_get.

## Phase 4 review/ship notes (deferred)

### D20 - Recurring-charge median on even occurrence counts (revisit: Phase 5 proactivity)
`recurring_charges` picks `amounts[len//2]` (upper-middle) as the "typical" charge, not the true
average-of-two-middles for an even count, and the 15%-consistency guard divides by that median with no
zero-guard. Harmless today (rejects rather than crashes); revisit when Phase 5 surfaces subscriptions.

### D21 - period_over_period pct is an unrounded Decimal (revisit: if surfaced)
The pct (`delta/prior*100`) can be a long non-terminating Decimal. It is internal today; quantize it
if/when it reaches a user surface.

### D22 - Lockfile for the now-large dep surface incl. plaid-python (extends D6/D16/D19)
`plaid-python` (floor-pinned `>=39.0`) pulls urllib3/dateutil/etc. No live CVE, but builds aren't
reproducible. Add a hash-pinned lockfile + an upper bound (`plaid-python>=39,<40`) and wire pip-audit
when CI lands. `redact.py` was broadened this phase to also scrub secret/access_token/client_id JSON
fields, and the `import --plaid` path is wrapped to never print a raw traceback.
