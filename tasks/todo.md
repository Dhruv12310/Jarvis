# Phase 0 — TODO

Tracking list for `/build`. One slice per commit; check sub-items as they pass. Full detail +
acceptance/verification in `tasks/plan.md`. Order is strict: 0 → A → B → C → D.

---

## [x] Task 0 — Scaffold + initial commit  ·  done in `d1531ab`
- [x] `jarvis/` importable; `jarvis/config.py` — one config object, `JARVIS_*` env-overridable, loads `.env`, makes `data/`
- [x] `pyproject.toml` — pkg + `python-dotenv`, `[dev] = pytest, ruff`, ruff/pytest config + `integration` marker
- [x] `.env.example` written; `.env` git-ignored
- [x] Verify: `pip install -e ".[dev]"`; `config.llm_model == "qwen3:14b"`; `ruff check .` + `pytest -q` green (7 passing)
- [x] Verify: initial commit made; `git status` clean (no clones/data)

## [x] Task A — Brain path  ·  `feat(core): ollama-backed orchestrator and CLI chat loop`
- [x] (source-driven) confirmed ollama 0.6.2: `generate(model, prompt)` -> `.response`; `embed` reserved for Slice C
- [x] `llm/client.py` — `LLMClient` protocol + `OllamaClient.generate`
- [x] `orchestrator.py` — `Orchestrator.chat(text)` -> `llm.generate(text)`, nothing else
- [x] `cli.py` + `__main__.py` — `python -m jarvis` REPL; clean exit
- [x] `pyproject.toml` += `ollama`
- [x] Verify: `test_orchestrator.py` (FakeLLMClient) green (10 passing), no network; `ruff` clean; wiring smoke OK
- [x] LIVE: `python -m jarvis` chat returns a real reply ("Hello, Dhruv!" from qwen3:14b)

### ▸ Checkpoint: Brain proven — units green w/o Ollama, manual chat returns a reply, review before stores

## [x] Task B — StructuredStore + SQLite  ·  `feat(stores): StructuredStore interface and SQLite notes`
- [x] `stores/structured.py` — `StructuredStore` ABC (`save_note`, `get_notes`) + frozen `Note`
- [x] `stores/sqlite_store.py` — `notes` table on init, `PRAGMA journal_mode=WAL`; **only** raw SQL here
- [x] `cli.py` — `:note <text>` save, `:notes` list (via interface, no SQL in CLI)
- [x] Verify: `test_structured_store.py` (temp DB) round-trip + persistence green; `test_cli.py` dispatch green; `ruff` clean (20 passing). Fully offline, no Ollama needed.

## [x] Task C — VectorStore + Chroma + embedder  ·  `feat(stores): VectorStore interface, Chroma backend, and local embedder`
- [x] (source-driven) confirmed chroma 1.5.9 BYO: `PersistentClient` + `get_or_create_collection` (no EF) + explicit `embeddings=`/`query_embeddings=`; ollama `embed(model, input)` -> `.embeddings`
- [x] `llm/embedder.py` — `Embedder` protocol + `OllamaEmbedder.embed`
- [x] `stores/vector.py` — `VectorStore` ABC (`add(...metadata=None)`, `query`) + frozen `VectorHit`
- [x] `stores/chroma_store.py` — persistent client, collection w/ **no** `embedding_function`, explicit `embeddings=`, telemetry off; **only** `chromadb` import here
- [x] `cli.py` — `:note` also embeds; `:recall <query>` returns top hit(s)
- [x] `pyproject.toml` += `chromadb`
- [x] Verify: `test_vector_store.py` (temp dir + deterministic fake embedder) top-hit green; `test_cli.py` full save/embed/recall green; `ruff` clean (26 passing). Offline.
- [x] LIVE: real `nomic-embed-text` similarity-read returns the right note (verified via selftest)

### ▸ Checkpoint: Both stores proven — units green w/o Ollama, note saved→listed→recalled, review before glue

## [x] Task D — DoD self-test + integration + boundary guards  ·  `test(core): Phase 0 DoD self-test and boundary guards`
- [x] `selftest.py` + `python -m jarvis selftest` — `generate` (non-empty) + both round-trips on seeded distinct notes; clean `PASS`/`FAIL` (backend errors caught)
- [x] `__main__.py` — subcommand dispatch (`selftest`)
- [x] `test_selftest.py` — offline fakes (pass/fail branches) + `@pytest.mark.integration` live test that auto-skips if Ollama down
- [x] `test_boundaries.py` — no SQL outside `sqlite_store.py`; no `chromadb` outside `chroma_store.py`; declared deps ⊆ approved set
- [x] Verify: `pytest -q` green w/o Ollama (31 passed, 1 skipped); `selftest` prints clean FAIL when Ollama down; `ruff` clean
- [x] LIVE: `python -m jarvis selftest` -> PASS; `pytest -m integration` green; full suite 32 passed, 0 skipped

### ▸ Checkpoint: Phase 0 DoD met + review done (2 findings fixed; 34 passed, live integration green). Next: `/code-simplify` → `/ship` (record Mulch learnings + forward-compat notes #3 cosine-vs-L2, #4 data-dir at ship).
