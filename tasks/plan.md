# Implementation Plan: Jarvis — Phase 2 (Organization)

> Derived from SPEC.md (validated; decisions locked). Implements Core spec Stages 1–3. Big phase, so
> the order PROTECTS the priority: signal capture lands first; calendar (the risk) is split read-first /
> write-deferrable. One vertical slice per commit. Phase 0–1 plans are in git history.

## Overview

Jarvis starts organizing: it logs every interaction (signal capture, Stage 1 — highest leverage, first),
has a real typed-MemoryRecord store with §7.1 retrieval (Stages 2–3), tracks goals, reads (and, if scope
allows, writes-with-confirmation) the user's Google Calendar, and produces an on-demand daily briefing.
Deterministic-first throughout; the LLM only phrases. Still reactive — no learning/proactivity.

## Architecture Decisions (locked in SPEC.md)

- **Signal capture first, always-on, cheap, non-blocking** — one append per interaction via
  StructuredStore; a logging failure is swallowed, never breaks a turn. Nothing learns from it yet.
- **Memory = typed MemoryRecord in a COSINE Chroma collection** (resolves D1) + deterministic §7.1
  recency+importance+relevance top-K; `last_accessed_at` bumped on retrieval via **VectorStore.upsert**
  (resolves D3). Importance is a heuristic. Memory population is EXPLICIT-only (notes/remember).
- **`:note`/`:recall` migrate to MemoryRecord** with a clean data migration (existing notes -> records,
  not orphaned); behavior preserved. The Phase 0 `notes` table is retired.
- **Calendar is the first PRIVATE integration** — Google libs (3 official) confined to `jarvis/calendar/`
  behind a new boundary guard; OAuth token + credentials.json are secrets in `./data/` (git-ignored);
  calendar data stays local. Writes only after explicit confirmation.
- **Briefing** assembles calendar + goals + a Phase-1 knowledge digest deterministically; the LLM phrases.
- New deps: the 3 google libs. No scheduler daemon, no async.

## Dependency Graph

```
Slice 1a  Signal capture  [FIRST - non-negotiable]
   SignalEvent + SignalLog + StructuredStore.save_signal/get_signals + wire into every CLI turn
        |
Slice 1b  Memory store + :note migration
   VectorStore.upsert (D3) + ChromaVectorStore cosine (D1)
   MemoryRecord + MemoryStore (save; §7.1 retrieve; bump last_accessed)
   migrate notes -> MemoryRecords; :note/:recall via MemoryStore; retire notes table
        |
Slice 2   Goals CRUD     StructuredStore goals table + Goal value object + :goal add/list/done
        |
Slice 3a  Calendar READ (OAuth)   [the risk - read first]
   +3 google deps; jarvis/calendar/{oauth,client}; calendar-auth flow; list_events; :cal
   boundary guard: google libs only under calendar/
        |
Slice 3b  Calendar confirmed-WRITE   [DEFERRABLE pressure-release valve]
   create_event; LLM proposes event from NL -> confirm gate -> execute; :schedule
        |
Slice 4   Daily briefing   assemble(today's calendar + active goals + knowledge digest) -> LLM phrases
```

Order: 1a (logging on) -> 1b (memory) -> 2 (goals) -> 3a (calendar read) -> 3b (calendar write, deferrable)
-> 4 (briefing needs goals + calendar-read + Phase 1 knowledge). 1a/1b/2 are independent of calendar.

## Task List

### Slice 1a — Signal capture (turn it ON first)
**Description:** Emit a structured `SignalEvent` for every interaction, appended via StructuredStore.
Cheap, append-only, swallow-on-failure. The single highest-leverage thing in the phase.

**Acceptance:**
- [ ] `signals/event.py`: frozen `SignalEvent(id, ts, kind, payload, session_id)` (Core §5.4).
- [ ] `stores/structured.py` + `sqlite_store.py`: `save_signal(event)` + `get_signals(limit)` on a new
  append-only `signals` table (raw SQL only in sqlite_store).
- [ ] `signals/log.py`: `SignalLog.emit(kind, payload)` builds + saves a SignalEvent under a per-session
  id; **catches and swallows any error** (never propagates into the interaction).
- [ ] `cli.py`: every turn (free-text question, each `:` command, briefing) emits a SignalEvent
  (kind + minimal payload: which path/connector ran, outcome). A `:signals` inspector command lists recent.

**Verification:** unit — emit grows the log; event shape; a forced StructuredStore failure does NOT
propagate. `pytest -q tests/test_signals.py` green; manual: run a few turns, `:signals` shows them. ruff clean.
**Files:** `signals/{__init__,event,log}.py`, `stores/structured.py`, `stores/sqlite_store.py`, `cli.py`,
`tests/test_signals.py`. **Scope:** M.
**Commit:** `feat(signals): append-only signal capture on every interaction`

### Checkpoint: Logging is ON
- [ ] Every interaction records a SignalEvent; capture failure can't break a turn. Review before memory.

### Slice 1b — Memory store + :note/:recall migration
**Source-driven first:** confirm Chroma cosine collection (`metadata={"hnsw:space":"cosine"}`) and
`collection.upsert` semantics on the installed chromadb.

**Acceptance:**
- [ ] `stores/vector.py` + `chroma_store.py`: add `upsert(id, text, embedding, metadata)` (D3); allow a
  `space` arg so the memory collection is **cosine** (D1); Phase 0 default unchanged for any remaining use.
- [ ] `memory/record.py`: frozen `MemoryRecord` (Core §5.1 fields).
- [ ] `memory/store.py`: `MemoryStore(vector, embedder)` with `save(record)` (embed + upsert into cosine
  collection, scalar fields in metadata) and `retrieve(query, k)` implementing **§7.1** deterministically
  (recency=exp(-λ·hrs), importance, relevance=cosine; normalize each to [0..1] over the candidate pool;
  weights from config; top-K; **bump last_accessed_at** via upsert). Importance heuristic helper.
- [ ] **Migration**: move existing `notes` rows -> MemoryRecords (type=observation, tier=observational),
  not orphaned; then retire the `notes` table path. `:note` -> `MemoryStore.save`; `:recall` ->
  `MemoryStore.retrieve`. Phase 0 `:note`/`:recall` behavior preserved.

**Verification:** unit — record round-trip; §7.1 ranking moves with recency/importance/relevance (fake
embedder); last_accessed bumped; migration moves notes without loss; `:note`/`:recall` still work.
Old `test_structured_store` note tests / `test_cli` note tests updated to the new model. ruff clean.
**Files:** `stores/vector.py`, `stores/chroma_store.py`, `memory/{__init__,record,store}.py`, `config.py`
(weights/λ/pool), `cli.py`, migration code (in sqlite_store or a small migrate helper),
`tests/test_memory_store.py`, updated note tests. **Scope:** L.
**Commit:** `feat(memory): typed MemoryRecord store with recency+importance+relevance retrieval`

### Checkpoint: Memory real
- [ ] MemoryRecords round-trip; §7.1 retrieval unit-tested; notes migrated, `:note`/`:recall` intact.

### Slice 2 — Goal / project memory
**Acceptance:**
- [ ] `stores/structured.py`: frozen `Goal(id, description, status, progress, priority, deadline, created_at)`;
  StructuredStore `save_goal`, `get_goals(status?)`, `update_goal(id, ...)` (status/progress).
- [ ] `sqlite_store.py`: `goals` table. `cli.py`: `:goal add <text>`, `:goals`, `:goal done <id>`.
  (LLM may optionally refine the phrasing; storage is deterministic.)

**Verification:** unit — add/list/update/complete round-trip + persistence (temp SQLite); CLI dispatch.
Each goal command emits a SignalEvent (Slice 1a). ruff clean.
**Files:** `stores/structured.py`, `stores/sqlite_store.py`, `cli.py`, `tests/test_goals.py`. **Scope:** M.
**Commit:** `feat(goals): goal/project CRUD via the structured store`

### Slice 3a — Calendar READ (Google OAuth)  [the risk; read first]
**Source-driven first:** verify against CURRENT Google docs — OAuth 2.0 InstalledApp flow (scopes:
`calendar.readonly` for this slice; `credentials.json` shape; token persistence/refresh) and Calendar v3
`events.list` (params, event resource: start/end dateTime vs date, summary).

**Acceptance:**
- [ ] pyproject += `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`; approved
  deps updated; boundary test: google libs imported only under `jarvis/calendar/`.
- [ ] config: `google_credentials_path` (`./data/credentials.json`), `google_token_path`
  (`./data/google_token.json`); both git-ignored.
- [ ] `calendar/oauth.py`: InstalledApp flow + token load/refresh/persist (the only google-auth importer).
- [ ] `calendar/client.py`: `CalendarClient(service)` with `list_events(time_min, time_max)` ->
  normalized `CalendarEvent`s (the only googleapiclient importer); a factory builds the authed service.
- [ ] `__main__.py`: `python -m jarvis calendar-auth` runs the one-time browser auth + persists the token.
- [ ] `cli.py`: `:cal` / `:agenda` lists today's/upcoming events (emits a `calendar_read` signal).
- [ ] **Docs:** a step-by-step Google Cloud setup note (project, enable API, Desktop client, consent
  screen TESTING + own account, download credentials.json to ./data/) in `docs/` or `.env.example`.

**Verification:** unit — inject a **fake Google service**; `list_events` normalizes the fake event
resource; no network. Integration (`-m integration`) skips unless `data/google_token.json` exists.
Manual: `calendar-auth` then `:cal` shows real events. ruff clean.
**Files:** `pyproject.toml`, `config.py`, `calendar/{__init__,oauth,client}.py`, `__main__.py`, `cli.py`,
`tests/test_calendar.py`, `tests/test_boundaries.py` (google guard), docs setup note. **Scope:** L.
**Commit:** `feat(calendar): read Google Calendar via OAuth (read-only)`

### Checkpoint: Calendar read works (briefing now has its data)
- [ ] Real events read post-OAuth; offline tests via fake service; boundary guard passes. **Decision
  point:** proceed to confirmed-write (3b) or, if OAuth ate the budget, defer 3b and go straight to the
  briefing (4) on read-only — the pressure-release valve.

### Slice 3b — Calendar confirmed-WRITE  [DEFERRABLE]
**Source-driven first:** verify Calendar v3 `events.insert` + the `calendar.events` write scope (re-auth
needed if the read-only token lacks write scope).

**Acceptance:**
- [ ] `calendar/client.py`: `create_event(event)` (events.insert).
- [ ] `cli.py`: `:schedule <natural language>` -> the LLM proposes a structured event (deterministic
  parse/validation of the proposal) -> CLI prints it -> user confirms `y` -> deterministic `create_event`.
  Never a silent mutation; a `calendar_write` signal on confirm.

**Verification:** unit — fake service; assert `create_event` is called ONLY after the confirm gate (a `n`
or non-confirm leaves the calendar untouched). Manual: `:schedule` then confirm creates a real event. ruff.
**Files:** `calendar/client.py`, `cli.py`, `tests/test_calendar.py`. **Scope:** M.
**Commit:** `feat(calendar): confirmed event creation (LLM proposes, user confirms, code executes)`

### Slice 4 — Daily briefing
**Acceptance:**
- [ ] `briefing.py`: deterministically assemble today's calendar events + active goals + a Phase-1
  knowledge digest (reuse the Knowledge pipeline for project/goal-relevant topics) into a DATA block; the
  LLM phrases it into a briefing; sources cited where it pulled live data.
- [ ] `cli.py`/`__main__.py`: a `briefing` command (emits a `briefing` signal). Empty sections handled
  (no calendar / no goals / no digest -> still a coherent briefing).

**Verification:** unit — fake calendar + goals + knowledge; assert the assembled block contains all three
and the LLM is given only that data; empty-section handling. Manual: `briefing` produces a grounded day
summary. ruff clean.
**Files:** `briefing.py`, `cli.py`, `__main__.py`, `tests/test_briefing.py`. **Scope:** M.
**Commit:** `feat(briefing): on-demand daily briefing (calendar + goals + knowledge digest)`

### Checkpoint: Phase 2 complete
- [ ] All DoD criteria met; signals logging since slice 1a; memory/goals/calendar/briefing work;
  `selftest` PASS; offline green; integration gated on OAuth. Proceed `/test` -> `/review` ->
  `/code-simplify` -> `/ship`.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Calendar OAuth balloons and starves the phase | High | Read-first (3a) feeds the briefing; write (3b) is a SEPARATE deferrable slice; ship read-only if needed |
| OAuth secrets leak (credentials.json/token) | High | Both in `./data/` git-ignored; boundary guard confines google libs to calendar/; redact from logs; consent screen TESTING + own account |
| Notes migration loses/orphans data | Med | Migration test asserts every existing note becomes a MemoryRecord; run before retiring the table |
| Chroma cosine/upsert behaves unexpectedly | Med | Source-driven verify cosine space + upsert before coding 1b |
| Google Calendar API drift | Med | Source-driven verify events.list/insert + OAuth flow at the start of 3a/3b |
| Signal capture slows/breaks a turn | Med | Cheap synchronous insert wrapped in swallow-on-failure; tested that errors don't propagate |
| Smuggling Phase 5 in | Med | Explicit-only memory population; NO reflection/user-model/ranking/auto-promotion; deterministic importance |

## Open Questions
- None blocking. API specifics verified per slice via source-driven-development. The 3a/3b split is the
  scope valve; the write decision is made at the post-3a checkpoint.

## Parallelization
- 1a must be first. 1b, 2 are independent of calendar (could parallelize across sessions; both touch
  cli.py and StructuredStore, so serialize there). 3a before 3b. 4 is a barrier (needs goals + calendar
  read + Phase 1 knowledge).
