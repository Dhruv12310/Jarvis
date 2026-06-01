# Spec: Jarvis — Phase 0 (Foundation)

> Per-phase implementation spec for the **active** phase. Design source-of-truth lives in
> `CLAUDE.md` (invariants) and `docs/Jarvis_Core_Spec.md` (Core subsystem). This document does not
> override those; it implements the smallest slice of them. When Phase 0 ships, this file is
> replaced by the Phase 1 spec.

## Objective

Prove the **brain works end-to-end** with the smallest possible skeleton that exercises the core
seams every later phase is built on. Nothing more.

The deliverable is a local CLI you run in a terminal that:
1. Takes a typed message, calls a **local** LLM (via Ollama), and prints the response.
2. Round-trips a write→read through **both** stores: save a note to the **StructuredStore** (SQLite)
   and read it back; embed a string into the **VectorStore** (Chroma) with a **local** embedder and
   find it by similarity.

**Who it's for:** the single user (dbhatt24), running on their own hardware. This is infrastructure
for future phases, not a user-facing product yet.

**Success looks like:** the four core seams — `LLMClient`, `Embedder`, `StructuredStore`,
`VectorStore` — exist behind clean interfaces, are wired through a thin orchestrator + CLI, and the
Definition of Done below passes on a real machine.

### Assumptions (correct me before I build)
1. **Default LLM = `qwen3:14b`** via Ollama, overridable by config/env. (Phi-4 = `phi4` is the
   alternate; both are named in the architecture diagram.)
2. **Embeddings come from Ollama** (`nomic-embed-text`), *not* sentence-transformers — this keeps the
   dependency set tiny (no PyTorch) and uses one local runtime for both generation and embedding.
3. **Chroma in bring-your-own-embeddings mode:** our `Embedder` produces vectors; Chroma only stores
   and similarity-searches them — every `add`/`query` passes `embeddings=` explicitly and the
   collection is created with **no** `embedding_function`, so Chroma's built-in embedder never runs
   (no model download, no hidden second embedder). `onnxruntime` may still install as a *transitive*
   dep — that's expected and is not counted by DoD #6 (which checks declared deps only).
4. **Orchestrator is stateless per turn** in Phase 0 (no conversation memory, no tools, no routing).
   In-session history is deferred (see Decisions).
5. **Ollama is already installed and running** locally; required models are pulled by the user
   (documented in Commands). The app does not install Ollama.
6. **No secrets in Phase 0** (fully local). `.env` is wired for *future* secrets and is git-ignored;
   Phase 0 has nothing to put in it.
7. **Python 3.11+**, dependency manager = `pip` + `pyproject.toml` + a venv.

## Tech Stack

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Per CLAUDE.md; type hints, dataclasses, ABCs |
| Local LLM | Ollama, model `qwen3:14b` (configurable) | Matches architecture diagram (Zone 1 Brain) |
| LLM/Embed client | `ollama` (official thin Python client) | One runtime for chat **and** embeddings; no heavy framework |
| Embedder | Ollama `nomic-embed-text` (configurable) | Local, free, no PyTorch |
| Structured store | stdlib `sqlite3` behind `StructuredStore` ABC | ACID transactions; impl sets `PRAGMA journal_mode=WAL` (cheap prep for the concurrent Heartbeat); per §5.0/§5.2 |
| Vector store | `chromadb` behind `VectorStore` ABC | Matches diagram (Chroma); BYO-embeddings |
| Config | `dataclass` + env vars, `.env` loaded via `python-dotenv` | One config location; secrets-ready |
| Tests | `pytest` | Standard, lightweight |
| Lint/format | `ruff` (check + format) | Single fast tool |

**Approved dependency set (runtime):** `ollama`, `chromadb`, `python-dotenv`.
**Approved dependency set (dev):** `pytest`, `ruff`.
Anything beyond this list is **Ask First** (see Boundaries). No agent frameworks (LangChain,
LlamaIndex, etc.) — the orchestrator is custom and small, per CLAUDE.md and open-decision #3.

## Commands

```bash
# One-time machine prerequisites (user runs these; app does not)
#   1. Install Ollama:  https://ollama.com/download
#   2. Pull models:
ollama pull qwen3:14b
ollama pull nomic-embed-text

# Project setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Windows PowerShell  (bash: source .venv/bin/activate)
pip install -e ".[dev]"               # installs runtime + dev deps from pyproject.toml

# Run the CLI chat loop
python -m jarvis

# Run the Definition-of-Done self-test (round-trips both stores + one live LLM call)
python -m jarvis selftest

# Tests
pytest -q                             # unit tests (no Ollama needed — LLM/embedder faked)
pytest -q -m integration              # integration tests (requires Ollama + models)

# Lint / format
ruff check .
ruff format .
```

## Project Structure

```
jarvis/
  __init__.py
  __main__.py          # entry point: `python -m jarvis` → CLI; `python -m jarvis selftest`
  config.py            # ONE config location: model names, host, db/vector paths (env-overridable)
  llm/
    __init__.py
    client.py          # LLMClient (Protocol) + OllamaClient.generate(prompt) -> str
    embedder.py        # Embedder (Protocol) + OllamaEmbedder.embed(text) -> list[float]
  orchestrator.py      # Orchestrator.chat(text) -> str  (calls LLMClient ONLY; no tools/routing)
  stores/
    __init__.py
    structured.py      # StructuredStore (ABC) + Note dataclass  (interface only)
    sqlite_store.py    # SQLiteStructuredStore  (the ONLY place raw SQL is allowed)
    vector.py          # VectorStore (ABC) + VectorHit dataclass (interface only)
    chroma_store.py    # ChromaVectorStore     (the ONLY place Chroma API is touched)
  cli.py               # REPL: plain text → chat; `:note`, `:notes`, `:recall` exercise the stores
tests/
  test_config.py
  test_structured_store.py   # SQLite round-trip, temp DB
  test_vector_store.py       # Chroma round-trip with a deterministic fake embedder
  test_orchestrator.py       # orchestrator with a fake LLMClient (no Ollama)
  test_selftest.py           # DoD round-trip; @pytest.mark.integration (needs Ollama)
pyproject.toml         # deps, scripts, ruff + pytest config
data/                  # runtime artifacts (git-ignored): jarvis.db, chroma/
.env.example           # documents future env vars; real .env is git-ignored
SPEC.md                # this file
```

## Code Style

Interfaces are abstract; implementations are the only place backend-specific code (SQL, Chroma) may
appear. Business logic (orchestrator, CLI) depends on the interface, never the implementation.

```python
# stores/structured.py — the seam. No SQL here.
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class Note:
    id: int
    content: str
    created_at: datetime

class StructuredStore(ABC):
    """Exact/relational facts. SQLite is the default backend; the interface keeps it swappable
    (JSON-tree later, per Core spec §5.0). Phase 0 implements notes only; domain methods
    (get_transactions, get_goals_for_project, save_event, ...) arrive in their own phases."""

    @abstractmethod
    def save_note(self, content: str) -> Note: ...

    @abstractmethod
    def get_notes(self, limit: int = 50) -> list[Note]: ...
```

```python
# orchestrator.py — deliberately thin. This is the whole Phase 0 orchestrator.
class Orchestrator:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def chat(self, text: str) -> str:
        return self._llm.generate(text)   # no tools, no routing, no cloud
```

```python
# stores/vector.py — similarity seam. metadata is optional NOW so later Core fields
# (type/importance/tier) can ride along without an interface change. We do NOT build
# MemoryRecord in Phase 0 — we just avoid painting the signature into a corner.
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

@dataclass(frozen=True)
class VectorHit:
    id: str
    text: str
    score: float                       # similarity/distance returned by Chroma
    metadata: dict | None = None

class VectorStore(ABC):
    @abstractmethod
    def add(self, id: str, text: str, embedding: Sequence[float],
            metadata: dict | None = None) -> None: ...

    @abstractmethod
    def query(self, embedding: Sequence[float], k: int = 5) -> list[VectorHit]: ...
```

Conventions:
- `snake_case` modules/functions, `PascalCase` classes, type hints on all public functions.
- `dataclass(frozen=True)` for value objects (`Note`, `VectorHit`).
- Interfaces as `abc.ABC`/`typing.Protocol`; depend on the seam, inject the implementation.
- One config object (`config.py`); no scattered `os.environ` reads in business logic.
- Conventional commits: `feat|fix|chore(scope): description` (per CLAUDE.md).

## Testing Strategy

- **Framework:** `pytest`. Tests live in `tests/`, mirroring `jarvis/` module names.
- **Unit (default, no Ollama):** stores and orchestrator are tested with fakes/temp backends.
  - `SQLiteStructuredStore` against a temp-file DB → save_note then get_notes returns it.
  - `ChromaVectorStore` against a temp dir, fed a **deterministic fake embedder** → add then query
    returns the right id as top hit. (Determinism without depending on a live model.)
  - `Orchestrator` with a `FakeLLMClient` that echoes → asserts wiring, no network.
- **Integration (`-m integration`, needs Ollama):** the DoD self-test — one real `generate`, one
  real `embed`, both store round-trips. Auto-skips (not fails) if Ollama is unreachable.
- **Coverage intent:** all deterministic code (config, both stores, orchestrator wiring, CLI command
  parsing) is unit-tested without a model. The model boundary is faked so the suite is fast and
  offline. No coverage % gate in Phase 0; the gate is "DoD passes + units green."

## Boundaries

- **Always:**
  - Program against `StructuredStore` / `VectorStore` / `LLMClient` / `Embedder` interfaces; inject
    implementations.
  - Keep **raw SQL only inside `sqlite_store.py`** and Chroma calls only inside `chroma_store.py`.
  - Keep all config in `config.py`; route any future secret through `.env` (git-ignored).
  - Run `pytest -q` and `ruff check .` before each commit; commit per vertical slice with a
    conventional message.
  - Keep everything local — the only network call is to `localhost` Ollama.
- **Ask First:**
  - Adding any dependency beyond {ollama, chromadb, python-dotenv, pytest, ruff}.
  - Changing a store/LLM interface signature.
  - Persisting conversation history or adding any cross-turn state to the orchestrator.
- **Never:**
  - Build anything from a later phase: signal capture, collectors/connectors, voice, UI, finance,
    proactivity/learning loop, cloud escalation / Model Router. (If tempted "while I'm here" — stop.)
  - Send anything off-machine; commit secrets or `.env`; put raw SQL/Chroma calls in the
    orchestrator, CLI, or any business logic.
  - Introduce a heavy agent framework.

## Success Criteria (Definition of Done — testable)

1. `python -m jarvis` opens a REPL; typing a message prints a **non-empty** response generated by the
   configured Ollama model.
2. `:note buy milk` persists a row via `StructuredStore.save_note`; `:notes` lists it back
   → **structured store write→read proven**.
3. Saving a note also embeds it via the local `Embedder` into Chroma; `:recall groceries` returns
   that note as the top similarity hit → **vector store embed→write→similarity-read proven**.
   (This leans on real-embedding semantics; the automated check in #4 seeds unambiguous data.)
4. `python -m jarvis selftest` performs steps 1–3 programmatically and prints a clear `PASS` (or a
   diagnostic `FAIL`). It **seeds a few clearly-distinct notes** and queries for one of them, so the
   expected note is unambiguously the closest hit — the assertion never depends on a fragile margin
   between similar strings.
5. `pytest -q` passes with **no Ollama running** (LLM + embedder faked).
6. Static checks hold: no raw SQL outside `sqlite_store.py`; no `chromadb` import outside
   `chroma_store.py`; the **directly declared** runtime deps in `pyproject.toml` ⊆ the approved set.
   This asserts against *declared* deps, **not** the installed tree — `chromadb` transitively pulls
   `onnxruntime`/`numpy`/`pydantic`/`tokenizers`, which is expected and fine. (Each is a grep-able
   assertion / test.)

## Decisions (resolved with the user — locked for Phase 0)

1. **Default LLM = `qwen3:14b`** (committed default). Phase 0 tests *plumbing*, not answer quality,
   so during dev loops the configurable default may point at a smaller/faster model and switch back —
   the committed default stays `qwen3:14b`.
2. **Embedder = Ollama `nomic-embed-text`** — avoids PyTorch, keeps the dependency set tiny.
3. **Orchestrator stays stateless per turn** — the smallest-skeleton choice; in-session history is
   not a seam Phase 0 proves, so it's deferred until it earns its place.
4. **Data location = `./data/`** (git-ignored) for `jarvis.db` + `chroma/`. `%LOCALAPPDATA%\Jarvis`
   is premature — deferred until there's a real install story.

## Build-time verifications (resolve via source-driven-development before the relevant slice)

Deferred on purpose — pin these against current upstream docs at build time, not now:
- **Ollama client method names (before Slices A & C).** Highest first-run-breakage risk: the `ollama`
  package has shifted between `generate`/`chat` and `embeddings`/`embed` across versions. Our wrapper
  API (`generate`, `embed`) is stable; confirm the *underlying* call names against the installed
  version before wiring.
- **Chroma BYO-embeddings (before Slice C).** Assumption #3 ("no hidden embedder") holds only if every
  `add`/`query` passes `embeddings=`/`query_embeddings=` explicitly and the collection is created with
  **no** `embedding_function`. Verify the calls are written that way. `onnxruntime` may still install
  transitively — expected, and does not violate DoD #6.

## Build Order (vertical slices → one commit each)

1. **Slice A — brain path:** `config` → `LLMClient`/`OllamaClient` → `Orchestrator` → `cli` chat loop.
   Commit: `feat(core): ollama-backed orchestrator + CLI chat loop`.
2. **Slice B — structured store:** `StructuredStore` ABC + `SQLiteStructuredStore` + `:note`/`:notes`
   + unit tests. Commit: `feat(stores): StructuredStore interface + SQLite notes`.
3. **Slice C — vector store:** `Embedder`/`OllamaEmbedder` + `VectorStore` ABC + `ChromaVectorStore`
   + `:recall` + unit tests. Commit: `feat(stores): VectorStore interface + Chroma + local embedder`.
4. **Slice D — DoD glue:** `selftest` command + integration test. Commit: `test(core): Phase 0 DoD self-test`.

Then: `/test` → `/review` → `/code-simplify` → `/ship` per CLAUDE.md before declaring Phase 0 done.
