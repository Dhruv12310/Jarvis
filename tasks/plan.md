# Implementation Plan: Jarvis — Phase 0 (Foundation)

> Derived from `SPEC.md` (validated). Build order is **one vertical slice per commit**. Do not build
> ahead of the current slice. A slice is done only when its acceptance criteria + verification pass.

## Overview

Stand up the smallest skeleton that proves the brain works end-to-end and exercises the four core
seams every later phase builds on: `LLMClient`, `Embedder`, `StructuredStore`, `VectorStore`. The
deliverable is a local CLI: type a message → local Ollama model responds; and a write→read
round-trips through **both** stores (SQLite note save/fetch; Chroma embed→similarity-find). Nothing
from later phases (signal capture, collectors, voice, UI, finance, proactivity, Model Router).

## Architecture Decisions (locked in SPEC.md)

- **Four seams behind interfaces; implementations are swappable and isolated.** Raw SQL lives only in
  `sqlite_store.py`; `chromadb` is imported only in `chroma_store.py`. Business logic (orchestrator,
  CLI) depends on the interface, never the backend.
- **One local runtime (Ollama) for both generation and embeddings** (`qwen3:14b` + `nomic-embed-text`)
  → no PyTorch, tiny dependency set.
- **Chroma in bring-your-own-embeddings mode** — every `add`/`query` passes `embeddings=` explicitly;
  collection created with no `embedding_function` (no hidden embedder). `onnxruntime` may install
  transitively — expected.
- **Orchestrator is stateless per turn** — no tools, no routing, no cloud, no memory.
- **One config location** (`jarvis/config.py`), env-overridable (`JARVIS_*`), `.env` for future
  secrets (git-ignored). Phase 0 has no secrets.
- **Dependencies introduced when their slice needs them** — `python-dotenv` (scaffold), `ollama`
  (Slice A), `chromadb` (Slice C). Dev: `pytest`, `ruff`.

## Dependency Graph

```
Task 0  Scaffold (pyproject, jarvis/, config.py, .env.example, initial commit)
   │
   ▼
Slice A  Brain path                 config → LLMClient/OllamaClient → Orchestrator → cli REPL → __main__
   │     (first end-to-end capability: chat)
   ▼
Slice B  Structured store           StructuredStore(ABC)+Note → SQLiteStructuredStore → cli :note/:notes
   │     (extends the Slice-A CLI; needs config.db_path)
   ▼
Slice C  Vector store               Embedder/OllamaEmbedder + VectorStore(ABC)+VectorHit → ChromaVectorStore
   │     (note-save hooks embedding; cli :recall) — after B because it extends the :note path
   ▼
Slice D  DoD glue                   selftest (live round-trip) + integration test + boundary guards
         (depends on A, B, C)
```

Order is strictly sequential (0 → A → B → C → D), one commit each. B and C share the CLI `:note`
path, so B precedes C to avoid integration friction. A must precede both (it creates the CLI +
orchestrator). D depends on all three.

## Task List

### Phase 0a: Scaffold

#### Task 0: Package skeleton, config, and initial commit
**Description:** Create the importable `jarvis` package, the single config location, the dependency
manifest (dev tooling + `python-dotenv` only at this point), and make the initial commit capturing
the current repo (spec, constitution, `.mulch`, docs, gitignore) plus the scaffold.

**Acceptance criteria:**
- [ ] `jarvis/` is importable; `jarvis/config.py` exposes one config object with `llm_model`
  (default `qwen3:14b`), `embed_model` (`nomic-embed-text`), `ollama_host`
  (`http://localhost:11434`), `db_path` (`./data/jarvis.db`), `vector_dir` (`./data/chroma`) — all
  overridable via `JARVIS_*` env vars; `.env` loaded via `python-dotenv`; `data/` created on demand.
- [ ] `pyproject.toml` declares the package, runtime dep `python-dotenv`, `optional-dependencies.dev
  = [pytest, ruff]`, and config for ruff + pytest (incl. `markers = ["integration: needs Ollama"]`).
- [ ] `.env.example` documents the `JARVIS_*` vars; real `.env` stays git-ignored.

**Verification:**
- [ ] `pip install -e ".[dev]"` succeeds.
- [ ] `python -c "from jarvis.config import config; print(config.llm_model)"` → `qwen3:14b`.
- [ ] `ruff check .` clean; `pytest -q` runs green (trivial `test_config.py`).
- [ ] `git log --oneline` shows the initial commit; `git status` clean (data/ ignored, no clones).

**Dependencies:** None.
**Files likely touched:** `pyproject.toml`, `jarvis/__init__.py`, `jarvis/config.py`, `.env.example`,
`tests/test_config.py`.
**Estimated scope:** S (1–2 substantive files).
**Commit:** `chore: initial commit — spec, constitution, and Phase 0 scaffold`

### Phase 0b: Brain path

#### Task A: Ollama-backed orchestrator + CLI chat loop
**Description:** The first end-to-end capability — text in → local model → text out — via a thin
orchestrator and a plain CLI REPL. No tools, no routing, no cloud.

**Acceptance criteria:**
- [ ] `jarvis/llm/client.py`: `LLMClient` protocol (`generate(prompt: str) -> str`) + `OllamaClient`
  using `config.llm_model` / `config.ollama_host`. *(First resolve the current `ollama` generation
  method name via source-driven-development — `generate` vs `chat`.)*
- [ ] `jarvis/orchestrator.py`: `Orchestrator(llm)` with `chat(text) -> str` returning
  `llm.generate(text)` — nothing else.
- [ ] `python -m jarvis` opens a REPL; a typed line prints a **non-empty** model response;
  `exit`/Ctrl-D quits cleanly.

**Verification:**
- [ ] Unit (no Ollama): `tests/test_orchestrator.py` with a `FakeLLMClient` (echo) →
  `pytest -q tests/test_orchestrator.py` green, no network.
- [ ] Manual (Ollama running): `python -m jarvis`, type "say hello", get a non-empty reply.
- [ ] `ruff check .` clean.

**Dependencies:** Task 0.
**Files likely touched:** `jarvis/llm/__init__.py`, `jarvis/llm/client.py`, `jarvis/orchestrator.py`,
`jarvis/cli.py`, `jarvis/__main__.py`, `tests/test_orchestrator.py`, `pyproject.toml` (+`ollama`).
**Estimated scope:** M.
**Commit:** `feat(core): ollama-backed orchestrator + CLI chat loop`

### Checkpoint: Brain proven
- [ ] `pytest -q` green with no Ollama; `ruff check .` clean.
- [ ] Manual chat returns a real model response.
- [ ] Review before proceeding to the stores.

### Phase 0c: The two stores

#### Task B: StructuredStore interface + SQLite notes
**Description:** Define the `StructuredStore` seam and ship the SQLite implementation backing a single
`notes` table; wire `:note`/`:notes` into the CLI to prove structured write→read.

**Acceptance criteria:**
- [ ] `jarvis/stores/structured.py`: `StructuredStore` ABC (`save_note(content) -> Note`,
  `get_notes(limit=50) -> list[Note]`) + frozen `Note(id, content, created_at)`.
- [ ] `jarvis/stores/sqlite_store.py`: `SQLiteStructuredStore` creates the `notes` table on init and
  sets `PRAGMA journal_mode=WAL`; **the only file containing raw SQL**.
- [ ] CLI: `:note <text>` saves; `:notes` lists most-recent-first; CLI calls the interface, no SQL.

**Verification:**
- [ ] Unit (no Ollama): `tests/test_structured_store.py` — temp DB, `save_note` then `get_notes`
  returns it with correct content/order. `pytest -q tests/test_structured_store.py` green.
- [ ] Manual: `:note buy milk` → `:notes` shows it; persists across a CLI restart.
- [ ] `ruff check .` clean.

**Dependencies:** Task 0; Task A (CLI to extend).
**Files likely touched:** `jarvis/stores/__init__.py`, `jarvis/stores/structured.py`,
`jarvis/stores/sqlite_store.py`, `jarvis/cli.py` (edit), `tests/test_structured_store.py`.
**Estimated scope:** M.
**Commit:** `feat(stores): StructuredStore interface + SQLite notes (WAL)`

#### Task C: VectorStore interface + Chroma + local embedder
**Description:** Add the local embedder and the vector seam with a Chroma implementation in
BYO-embeddings mode; saving a note now also embeds it, and `:recall` finds notes by similarity.

**Acceptance criteria:**
- [ ] `jarvis/llm/embedder.py`: `Embedder` protocol (`embed(text) -> list[float]`) + `OllamaEmbedder`
  (`config.embed_model`). *(Resolve the current `ollama` embeddings method name via
  source-driven-development — `embeddings` vs `embed`.)*
- [ ] `jarvis/stores/vector.py`: `VectorStore` ABC (`add(id, text, embedding, metadata=None)`,
  `query(embedding, k=5) -> list[VectorHit]`) + frozen `VectorHit(id, text, score, metadata=None)`.
- [ ] `jarvis/stores/chroma_store.py`: `ChromaVectorStore` — persistent client at `config.vector_dir`,
  collection created with **no** `embedding_function`, `add`/`query` pass `embeddings=` explicitly;
  **the only file importing `chromadb`**.
- [ ] CLI: saving a `:note` also embeds it into the vector store; `:recall <query>` returns the top
  similarity hit(s).

**Verification:**
- [ ] Unit (no Ollama): `tests/test_vector_store.py` — temp dir + a **deterministic fake embedder**
  (e.g. bag-of-words → fixed-dim vector); add 3 distinct texts, query returns the expected id as top
  hit. `pytest -q tests/test_vector_store.py` green.
- [ ] Manual (Ollama): `:note "dentist appointment friday"` then `:recall "doctor visit"` surfaces it.
- [ ] `ruff check .` clean.

**Dependencies:** Task 0; Task A (CLI); Task B (extends the `:note` save path).
**Files likely touched:** `jarvis/llm/embedder.py`, `jarvis/stores/vector.py`,
`jarvis/stores/chroma_store.py`, `jarvis/cli.py` (edit), `tests/test_vector_store.py`,
`pyproject.toml` (+`chromadb`).
**Estimated scope:** M.
**Commit:** `feat(stores): VectorStore interface + Chroma + local embedder`

### Checkpoint: Both stores proven
- [ ] `pytest -q` green with no Ollama (orchestrator + both stores faked/temp).
- [ ] Manual: note saved → listed (SQLite) and recalled by similarity (Chroma).
- [ ] Review before the DoD glue.

### Phase 0d: Definition-of-Done glue

#### Task D: Phase 0 self-test + integration + boundary guards
**Description:** Tie it together with a programmatic DoD self-test, a live integration test, and the
grep-able architecture boundary tests that turn the spec's rules into automated checks.

**Acceptance criteria:**
- [ ] `jarvis/selftest.py` + `python -m jarvis selftest`: one live `generate` (assert non-empty),
  seed a few **clearly-distinct** notes, structured round-trip, and embed→similarity-read for a
  queried note that is unambiguously closest; print `PASS` or a diagnostic `FAIL`.
- [ ] `tests/test_selftest.py` (`@pytest.mark.integration`): asserts non-empty model output + both
  round-trips; **auto-skips** (not fails) if Ollama is unreachable.
- [ ] `tests/test_boundaries.py`: (1) no raw SQL outside `sqlite_store.py`; (2) no `chromadb` import
  outside `chroma_store.py`; (3) declared runtime deps in `pyproject.toml` ⊆ {ollama, chromadb,
  python-dotenv} — asserts against **declared** deps, not the installed tree.

**Verification:**
- [ ] `pytest -q` (units + boundaries) green with **no Ollama**.
- [ ] `pytest -q -m integration` green with Ollama + models pulled.
- [ ] `python -m jarvis selftest` prints `PASS`.
- [ ] `ruff check .` clean.

**Dependencies:** Tasks A, B, C.
**Files likely touched:** `jarvis/selftest.py`, `jarvis/__main__.py` (edit: subcommand dispatch),
`tests/test_selftest.py`, `tests/test_boundaries.py`.
**Estimated scope:** M.
**Commit:** `test(core): Phase 0 DoD self-test + boundary guards`

### Checkpoint: Phase 0 complete
- [ ] All four DoD success criteria from `SPEC.md` met; `selftest` PASS; units + integration green.
- [ ] Proceed `/test` → `/review` → `/code-simplify` → `/ship` (per CLAUDE.md) before declaring done.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `ollama` package method-name drift (`generate`/`chat`, `embeddings`/`embed`) | High likelihood / Med | Resolve via source-driven-development at the start of Slices A & C; the wrapper interface isolates blast radius to one file |
| Chroma pulls `onnxruntime`/heavy install (esp. Windows) | Med | Expected & allowed; DoD #6 checks declared deps only; verify BYO-embeddings call shape so the default embedder never runs |
| `qwen3:14b` VRAM/availability on the dev machine | Med | Default stays `qwen3:14b`; point the configurable default at a smaller model during dev loops |
| Real-embedding similarity flakiness in `selftest` | Med/Low | Seed unambiguous, distinct notes so the target is clearly closest; unit tests use a deterministic fake embedder |
| Windows path / Chroma persistence quirks under `data/` | Low/Med | `pathlib` + config-driven paths; `mkdir` on demand; never hard-code separators |

## Open Questions
- None blocking. The two build-time verifications (ollama method names; Chroma BYO call shape) are
  tracked inside Slices A and C and resolved there via source-driven-development.

## Parallelization
- Strictly sequential for a single builder (0 → A → B → C → D), commit per slice.
- If parallelized across sessions: B and C interface files (`structured.py`/`vector.py`) could be
  drafted independently, but the shared CLI `:note` integration serializes B before C. A must land
  first. D is a barrier (needs all three).
