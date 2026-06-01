# Decisions Log (Jarvis)

Lightweight ADR-style log. Phase 0 established the foundation; the items below were surfaced during
the Phase 0 build, review, and ship gate and deliberately deferred. Revisit each in the noted phase.

> The project intends to track this in Mulch (`ml record`), but the `ml`/`mulch` CLI is not installed
> in this environment, so decisions are recorded here for now. Port to Mulch once the CLI is available
> (the `.mulch/` store already exists).

## Deferred decisions (revisit in the noted phase)

### D1 - Vector distance metric: Chroma default L2 vs SPEC 7.1 cosine (revisit: Phase 2 retrieval)
`ChromaVectorStore` uses Chroma's default collection space (squared L2). SPEC 7.1 defines retrieval
relevance as cosine similarity, and nomic-embed-text vectors are not normalized, so L2 and cosine
rank differently. Fine for Phase 0 (plumbing). When Phase 2 builds real retrieval scoring, create the
collection with `metadata={"hnsw:space": "cosine"}` (or normalize embeddings). Until then, treat
`VectorHit.distance` as a backend distance, not a spec "relevance".

### D2 - Data directory tied to source location (revisit: Phase 2 Heartbeat)
`config._ROOT = Path(__file__).resolve().parent.parent` anchors `data/` to the source tree. Correct
for the editable Phase 0 install; breaks for a packaged/non-editable install or a Heartbeat service
running from a different CWD. Move to a user/OS data dir (e.g. platformdirs or %LOCALAPPDATA%) when
the Heartbeat becomes a real long-lived service.

### D3 - Chroma add vs upsert on duplicate id (revisit: when records are re-embedded)
`ChromaVectorStore.add()` silently keeps the old document if an id already exists (Chroma logs, does
not raise). Safe in Phase 0 because vector ids are the append-only SQLite note id (never reused). The
moment any phase re-embeds or updates a record, switch to `collection.upsert(...)` to avoid silent
data loss. A code comment at the call site noting the append-only assumption would help.

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
