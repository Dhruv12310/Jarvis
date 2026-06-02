# Spec: Jarvis — Phase 2 (Organization)

> Per-phase implementation spec for the **active** phase. Phases 0–1 are shipped; their specs live in
> git history. Design source-of-truth: `CLAUDE.md` (invariants) and **`docs/Jarvis_Core_Spec.md`**
> (this phase implements Stages 1–3 of the Core: read §5 memory model, §6 Stages 1–3, §7.1 retrieval,
> §10 phasing). Phase 0–1 learnings + deferred decisions: `docs/DECISIONS.md` (this phase resolves
> **D1** cosine and **D3** upsert).

## Objective

Jarvis starts **organizing my life**: it knows my schedule and goals, gives me an on-demand daily
briefing, and — most importantly — **begins recording what I do** so later phases can learn from it.
Still reactive; no learning or proactivity yet.

The non-negotiable framing (Core spec §10): **signal capture turns on FIRST.** Every day it is off is
training data lost forever; Phase 5's proactivity engine is worthless without accumulated history.
Nothing learns from the signals in Phase 2 — the entire point is to start the log now.

**Who it's for:** the single user (dbhatt24), at the CLI. Calendar is the **first private-data
integration** — personal data stays local (a refinement of the trust boundary, below).

### Assumptions (correct me before I build)
1. **Signal capture is a cheap synchronous append** — one SQLite INSERT per interaction via
   `StructuredStore`, wrapped so a logging failure never breaks or slows the interaction. No async/queue
   (that pairs with the always-on Heartbeat infra, not now).
2. **MemoryRecords live in the vector store** (Core §5: episodic/semantic → vector store), with their
   scalar fields (type/importance/tier/confidence/timestamps/source) in Chroma metadata and the content
   as the document. Exact facts (goals, calendar) go to the `StructuredStore`.
3. **`:note`/`:recall` migrate to the real MemoryRecord model** — Phase 0's notes table + raw vector add
   is replaced by `MemoryStore` (typed MemoryRecord + §7.1 retrieval). The Phase 0 `notes` table is
   retired. (Open Question — confirm.)
4. **Memory retrieval uses cosine** (resolves D1): the memory collection is created with
   `hnsw:space="cosine"` so §7.1 relevance is real cosine similarity.
5. **Calendar uses the official Google client** (`google-api-python-client` + `google-auth-oauthlib`),
   the InstalledApp (desktop) OAuth flow, with the token persisted to `data/` (git-ignored). You create a
   Google Cloud OAuth **Desktop** client and drop `credentials.json` in (user setup, documented).
6. **Importance at write time is a heuristic** (Core §11 allows heuristic-first) — a deterministic
   default/length-or-keyword score in [0..1], NOT an LLM call. No reflection.
7. **Calendar writes require explicit confirmation** — the LLM proposes a structured event, the CLI
   prints it, you type `y`, then deterministic code calls Google. Never a silent mutation.

## Trust boundary (refined for the first private integration)

The Phase 1 rule was "only Collectors cross out, to PUBLIC data." Phase 2 adds a **private** outbound
path: Calendar OAuth talks to Google **only to fetch/modify YOUR own authorized data**, which then
**stays local** (never re-shared with any other service). Enforced:
- Calendar (Google client) code lives only under `jarvis/calendar/`; a boundary test asserts the google
  libs are imported nowhere else (mirroring the `httpx`-only-in-`connectors/` guard).
- OAuth tokens + `credentials.json` are git-ignored, read from `data/`/secrets only, never logged.
- The user's calendar data is summarized/used locally; nothing private goes to the public connectors or
  off-machine.

## Tech Stack

| Concern | Choice | Why |
|---|---|---|
| Signals / goals / calendar facts | `StructuredStore` (SQLite) | Exact/relational; append-only signal log; goals CRUD |
| Memory (episodic/semantic) | `MemoryStore` over Chroma (**cosine**) + Ollama embedder | Core §5; §7.1 retrieval; resolves D1 |
| Calendar | `google-api-python-client` + `google-auth-oauthlib` + `google-auth-httplib2` | Official OAuth + Calendar v3; the only new deps |
| Routing / phrasing | Ollama local LLM (Phase 0–1 `LLMClient`) | LLM only phrases (briefing, goal refine, event parse) |
| Config / secrets | `config.py` + `.env` + `data/` token files (git-ignored) | OAuth tokens never committed |
| Tests | `pytest` (+ mocked Google service, fake LLM/embedder) | Offline; integration gated on OAuth |

**Approved runtime deps (updated):** `python-dotenv`, `ollama`, `chromadb`, `httpx`,
**`google-api-python-client`**, **`google-auth-oauthlib`**, **`google-auth-httplib2`**.
No scheduler daemon, no framework, no async infra.

## Commands

```bash
# One-time: Google Calendar OAuth (you create a Desktop OAuth client in Google Cloud Console,
# enable the Calendar API, download credentials.json into ./data/, then authorize once):
python -m jarvis calendar-auth      # opens a browser; persists data/google_token.json (git-ignored)

python -m jarvis                    # CLI: ask, :goal/:goals, calendar, briefing; every turn logs a signal
python -m jarvis selftest           # DoD self-test (offline-safe parts + live where creds exist)

pytest -q                           # offline (Google service + LLM + embedder mocked)
pytest -q -m integration            # live: HN always; markets/news/calendar only if keys/OAuth present
ruff check . ; ruff format --check .
```

## Project Structure

```
jarvis/
  signals/
    __init__.py
    event.py          # SignalEvent value object (Core §5.4)
    log.py            # SignalLog: emit(event) -> StructuredStore append; never raises into callers
  memory/
    __init__.py
    record.py         # MemoryRecord value object (Core §5.1)
    store.py          # MemoryStore: save() + retrieve() with the §7.1 recency+importance+relevance score
  calendar/
    __init__.py
    oauth.py          # InstalledApp OAuth flow + token persistence (the ONLY google-auth importer)
    client.py         # CalendarClient: list_events(), create_event()  (the ONLY googleapiclient importer)
  briefing.py         # assemble(calendar + goals + knowledge digest) deterministically -> LLM phrases
  stores/
    structured.py     # + SignalEvent/Goal value objects; StructuredStore += save_signal/get_signals,
                      #   save_goal/get_goals/update_goal
    sqlite_store.py   # + signals, goals tables (raw SQL stays here)
    vector.py         # + upsert(...) (resolves D3) ; collection/space params
    chroma_store.py   # + upsert ; cosine-space collection
  config.py           # + memory weights (w_rec/w_imp/w_rel), recency lambda, candidate pool K;
                      #   google credentials_path / token_path
  cli.py              # signal capture on EVERY turn; :goal add/list/done; :cal / :schedule; briefing
tests/
  test_signals.py  test_memory_store.py  test_goals.py
  test_calendar.py (mocked google service)  test_briefing.py  test_boundaries.py (extended)
  (Phase 0–1 tests remain; :note/:recall tests migrate to MemoryStore)
```

## Code Style

Deterministic code owns capture/storage/retrieval/scoring/CRUD/calendar; the LLM only phrases.

```python
# signals/event.py — Core §5.4. Dumb, cheap, append-only.
@dataclass(frozen=True)
class SignalEvent:
    id: str                 # uuid
    ts: datetime
    kind: str               # "query" | "command" | "briefing" | "goal_added" | "calendar_read" | ...
    payload: dict           # topic(s), connector(s)/path, outcome, etc. (json)
    session_id: str         # uuid per CLI session
```

```python
# memory/record.py — Core §5.1. The core memory object (episodic + semantic).
@dataclass(frozen=True)
class MemoryRecord:
    id: str
    type: str               # observation|preference|decision|pattern|outcome|reflection
    content: str
    created_at: datetime
    last_accessed_at: datetime
    importance: float        # [0..1], heuristic at write time (Phase 2)
    tier: str               # foundational|tactical|observational
    confidence: float        # [0..1]
    source: str             # interaction|collector|reflection|feedback
    links: list[str]         # related record ids
    metadata: dict
```

```python
# memory/store.py — Stage 3 retrieval is DETERMINISTIC (Core §7.1). The LLM is not involved.
#   retrieval_score(m,q) = w_rec*recency(m) + w_imp*importance(m) + w_rel*relevance(m,q)
#   recency(m)   = exp(-lambda * hours_since(m.last_accessed_at))
#   relevance    = cosine(embed(q), m.embedding)        # cosine collection (D1)
#   normalize each term to [0..1] over the candidate set, then weight; return top-K; bump last_accessed.
```

Conventions (carry forward): type hints, frozen dataclasses for value objects, `abc.ABC`/`Protocol`
seams, one config location, conventional commits, ruff clean. **Secrets:** OAuth tokens/credentials read
from `data/`/env only; never logged, never committed; redact from errors (per `security-and-hardening`).

## Testing Strategy

- **Signals (unit):** every CLI turn emits a `SignalEvent`; assert the log grows and the event shape; a
  forced StructuredStore failure does NOT propagate (capture never breaks an interaction).
- **Memory (unit):** save typed MemoryRecords; `retrieve` returns top-K by the §7.1 score with a fake
  embedder — assert recency/importance/relevance each move ranking as expected, and that
  `last_accessed_at` is bumped (upsert, D3). Cosine space verified.
- **Goals (unit):** add/list/update/complete round-trip via a temp SQLite StructuredStore.
- **Calendar (unit):** inject a **fake Google service** (no network); assert `list_events` normalizes
  events and `create_event` is called only after a confirmation gate (LLM-proposed → confirmed → execute).
- **Briefing (unit):** fake calendar + goals + knowledge; assert deterministic assembly feeds the LLM a
  data block (calendar + goals + sourced digest) and empty sections are handled.
- **Integration (`-m integration`):** real Google Calendar gated on OAuth token presence (skips like the
  keyed connectors skip without keys); HN still live.
- **Boundaries (extended):** google libs imported only under `calendar/`; httpx only in `connectors/`;
  SQL only in sqlite modules; no connector imports another; declared deps ⊆ approved set.

## Boundaries

- **Always:**
  - **Log a SignalEvent on every interaction** (append-only, cheap, non-blocking, swallow-on-failure).
  - Deterministic: signal logging, memory storage, §7.1 scoring, goal CRUD, calendar read/parse, briefing
    assembly. The LLM ONLY phrases (briefing prose, goal refine, natural-language event parse to a proposal).
  - Calendar writes only after explicit user confirmation; reads/writes via the CalendarClient seam.
  - Storage behind interfaces (StructuredStore / VectorStore / MemoryStore); raw SQL only in sqlite
    modules, Chroma only in chroma_store, google libs only in `calendar/`.
  - OAuth tokens/credentials via `data/`/secrets, git-ignored, redacted from logs; calendar data stays local.
  - `pytest` + `ruff` before each commit; conventional commits; commit per slice.
- **Ask First:**
  - Adding any dependency beyond the approved set (+ the three google libs).
  - Changing the StructuredStore / VectorStore / MemoryStore interfaces.
  - Retiring the Phase 0 notes table (the `:note` → MemoryRecord migration).
- **Never:**
  - Build Phase 5 (reflection, user model, proactivity/ranking, feedback, explore/exploit); voice; UI /
    the Jarvis feed (Phase 3); finance (Phase 4); cloud / Model Router; an always-on scheduler that
    auto-fires the briefing (on-demand only).
  - Let signal capture block/slow an interaction; silently mutate the real calendar; commit OAuth secrets;
    leak private calendar data off-machine or to the public connectors.

## Success Criteria (Definition of Done — testable)

1. **Signal capture is ON:** every interaction (query, command, briefing) writes a `SignalEvent` to the
   append-only log; I can inspect the log and see the turns recorded. A capture failure never breaks a turn.
2. **Goals persist:** I can add and list goals (and mark done); they survive a restart (StructuredStore).
3. **Calendar reads:** after `calendar-auth`, Jarvis shows today's/upcoming events from my real Google
   Calendar; it creates an event **only after I confirm** an LLM-proposed event.
4. **Briefing:** a `briefing` command produces a grounded summary of my day (today's calendar + active
   goals + a relevant knowledge digest), with sources where it pulled live data.
5. **Memory:** the `MemoryStore` round-trips typed `MemoryRecord`s; basic §7.1 (recency+importance+
   relevance) top-K retrieval works and is unit-tested; `last_accessed_at` is bumped on retrieval.
6. **Static guards:** google libs only under `calendar/`; storage seams respected; deps ⊆ approved set.
7. `pytest -q` passes fully offline (Google service + LLM + embedder mocked); `-m integration` passes the
   HN path live and the Calendar path when OAuth is present; `selftest` PASS.

## Decisions (resolved with the user — locked for Phase 2)

1. **Migrate `:note`/`:recall` to MemoryRecord; retire the `notes` table** — as a CLEAN migration: move
   any existing `notes` rows into MemoryRecords (do not orphan them), and keep `:note`/`:recall` working
   through the new model (no Phase 0 DoD regression).
2. **Google = 3 official libs** (`google-api-python-client`, `google-auth-oauthlib`,
   `google-auth-httplib2`), confined to `jarvis/calendar/` behind a new boundary guard. (Hand-rolling
   OAuth is a false economy — refresh/expiry are exactly the security-sensitive parts to delegate.)
3. **User does the Google Cloud OAuth setup once** (documented step-by-step): create a project, enable the
   Calendar API, make a **Desktop** OAuth client, set the consent screen to **TESTING** mode with only the
   user's own account, download `credentials.json` into `./data/`. `credentials.json` + the generated
   token are **secrets** in `./data/` (git-ignored) — a leaked OAuth client is worse than a leaked API key.
4. **Memory population is EXPLICIT-only** in Phase 2 — the signal log is the raw cheap history; memory is
   explicit (notes/`remember`) only. NO auto-promotion of signals to memories (that is a Stage-4/5
   reflection-engine policy and would pollute memory with un-curated noise before pruning exists).
5. **Importance = deterministic heuristic** default (~0.5, bumped for explicit "remember"/length).
   Refined in Phase 5; no LLM importance call now.
6. **`SPEC.md` is the Phase 2 spec**; a copy is kept at `docs/specs/phase-2.md` (Phase 1 in git history).
7. **Scope guardrails:** signal capture goes in FIRST (non-negotiable — every day off is lost training
   data). Calendar is the risk: built **READ-ONLY first** (it is what the briefing needs), then
   confirmed-write as a SEPARATE deferrable sub-slice. **Pressure-release valve:** if OAuth balloons, ship
   read-only in Phase 2 and defer confirmed-write to a small follow-on. Aim for read + confirmed-write;
   do not let write-support blow up the phase.

## Build-time verifications (source-driven-development, at the start of the relevant slice)

- **Calendar slice:** verify against CURRENT Google docs — the OAuth 2.0 InstalledApp flow (scopes,
  `credentials.json` shape, token refresh/persistence) and Calendar API v3 `events.list` / `events.insert`
  (params, the event resource shape: start/end dateTime vs date, summary, attendees).
- **Memory slice:** confirm Chroma cosine-space collection creation (`metadata={"hnsw:space":"cosine"}`)
  and `collection.upsert` semantics on the installed chromadb.

## Build Order (for /plan to slice — this is a big phase)

1. **Signal capture + the real memory store** — the substrate; **start logging immediately** (highest
   priority). SignalEvent + SignalLog + StructuredStore signals table; MemoryRecord + MemoryStore (cosine,
   upsert, §7.1 retrieval); migrate `:note`/`:recall`. Wire signal emit into every CLI turn.
2. **Goal / project memory** — StructuredStore goals CRUD + `:goal` commands.
3. **Calendar (Google OAuth)** — its own careful slice; source-driven verify; `calendar-auth` flow; read
   events; then confirmed writes (LLM proposes → confirm → execute).
4. **Daily briefing** — deterministic assembly (calendar + goals + knowledge digest) + LLM phrasing.

Then `/test` → `/review` → `/code-simplify` → `/ship` per CLAUDE.md.
