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
