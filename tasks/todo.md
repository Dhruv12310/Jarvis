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
- [ ] PENDING Ollama: live `python -m jarvis` returns a non-empty reply (needs Ollama running + `qwen3:14b` pulled)

### ▸ Checkpoint: Brain proven — units green w/o Ollama, manual chat returns a reply, review before stores

## [x] Task B — StructuredStore + SQLite  ·  `feat(stores): StructuredStore interface and SQLite notes`
- [x] `stores/structured.py` — `StructuredStore` ABC (`save_note`, `get_notes`) + frozen `Note`
- [x] `stores/sqlite_store.py` — `notes` table on init, `PRAGMA journal_mode=WAL`; **only** raw SQL here
- [x] `cli.py` — `:note <text>` save, `:notes` list (via interface, no SQL in CLI)
- [x] Verify: `test_structured_store.py` (temp DB) round-trip + persistence green; `test_cli.py` dispatch green; `ruff` clean (20 passing). Fully offline, no Ollama needed.

## [ ] Task C — VectorStore + Chroma + embedder  · `feat(stores): VectorStore interface + Chroma + local embedder`
- [ ] (source-driven) confirm current `ollama` embeddings method name
- [ ] `llm/embedder.py` — `Embedder` protocol + `OllamaEmbedder.embed`
- [ ] `stores/vector.py` — `VectorStore` ABC (`add(...metadata=None)`, `query`) + frozen `VectorHit`
- [ ] `stores/chroma_store.py` — persistent client, collection w/ **no** `embedding_function`, explicit `embeddings=`; **only** `chromadb` import here
- [ ] `cli.py` — `:note` also embeds; `:recall <query>` returns top hit(s)
- [ ] `pyproject.toml` += `chromadb`
- [ ] Verify: `test_vector_store.py` (temp dir + deterministic fake embedder) top-hit green; manual `:recall` works; `ruff` clean

### ▸ Checkpoint: Both stores proven — units green w/o Ollama, note saved→listed→recalled, review before glue

## [ ] Task D — DoD self-test + integration + boundary guards  · `test(core): Phase 0 DoD self-test + boundary guards`
- [ ] `selftest.py` + `python -m jarvis selftest` — live `generate` (non-empty) + both round-trips on seeded distinct notes; `PASS`/`FAIL`
- [ ] `__main__.py` — subcommand dispatch (`selftest`)
- [ ] `test_selftest.py` — `@pytest.mark.integration`, auto-skips if Ollama down
- [ ] `test_boundaries.py` — no SQL outside `sqlite_store.py`; no `chromadb` outside `chroma_store.py`; declared deps ⊆ approved set
- [ ] Verify: `pytest -q` green w/o Ollama; `pytest -q -m integration` green w/ Ollama; `selftest` PASS; `ruff` clean

### ▸ Checkpoint: Phase 0 complete — all SPEC.md DoD met → `/test` → `/review` → `/code-simplify` → `/ship`
