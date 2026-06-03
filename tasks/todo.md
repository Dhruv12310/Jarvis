# Phase 2 — TODO

Tracking list for `/build`. One vertical slice per commit. Full detail in `tasks/plan.md`.
Deterministic-first: LLM only phrases. **Signal capture goes in FIRST (non-negotiable).**

---

## [x] Slice 1a — Signal capture (turn it ON first)  ·  `feat(signals): append-only signal capture on every interaction`
- [x] `signals/event.py` `SignalEvent(id, ts, kind, payload, session_id)` (Core §5.4)
- [x] `StructuredStore` += `save_signal`/`get_signals`; `signals` append-only table (raw SQL in sqlite_store)
- [x] `signals/log.py` `SignalLog.emit` (per-session id; swallow-on-failure, never breaks a turn)
- [x] `cli.py` — every turn emits a SignalEvent (query/command/error); `:signals` inspector
- [x] Verify: unit (append/order/persist, swallow-on-failure, loop emits per turn); 105 offline green; ruff clean

### ▸ Checkpoint: Logging is ON — review before memory

## [x] Slice 1b — Memory store + :note migration  ·  `feat(memory): real MemoryRecord store with deterministic retrieval`
- [x] (source-driven) verify Chroma cosine collection + `upsert` on installed chromadb
- [x] `vector.py`/`chroma_store.py` += `upsert` (D3) + cosine `space` (D1) + `list_all`
- [x] `memory/record.py` `MemoryRecord` (§5.1); `memory/store.py` `MemoryStore.save` + `.retrieve` (§7.1: recency+importance+relevance, normalized top-K, bump last_accessed)
- [x] importance heuristic; memory population EXPLICIT-only (`remember(explicit=True)`)
- [x] MIGRATION: existing notes -> MemoryRecords (no orphans); drain notes table (idempotent); `:note`/`:recall` via MemoryStore (behavior preserved)
- [x] Verify: unit (round-trip, §7.1 ranking, last_accessed bump, migration no-loss); `:note`/`:recall` intact; 119 green; ruff clean

### ▸ Checkpoint: Memory real

## [x] Slice 2 — Goals CRUD  ·  `feat(goals): goal/project CRUD via the structured store`
- [x] `Goal(id, description, status, progress, priority, deadline, created_at)`; StructuredStore save/get/update_goal; `goals` table
- [x] `cli.py` — `:goal add <text>`, `:goals`, `:goal done <id>` (each emits a signal)
- [x] Verify: unit (CRUD + persistence + CLI dispatch); 132 green; ruff clean

## [x] Slice 3a — Calendar READ (OAuth)  ·  `feat(calendar): read Google Calendar via OAuth (read-only)`   [the risk; read first]
- [x] (source-driven) verify Google OAuth InstalledApp flow + Calendar v3 `events.list` + event resource shape
- [x] pyproject += 3 google libs; approved deps updated; boundary guard: google libs only under `calendar/`
- [x] config: `google_credentials_path`/`google_token_path` (./data/, git-ignored)
- [x] `calendar/oauth.py` (flow + token persist/refresh); `calendar/client.py` `list_events` -> CalendarEvent
- [x] `__main__.py` `calendar-auth`; `cli.py` `:cal`/`:agenda`; docs: step-by-step Google Cloud setup (Desktop client, consent TESTING + own account, credentials.json -> ./data/)
- [x] Verify: unit (fake google service normalization, query params, oauth guard paths); 141 green; ruff clean
- [x] LIVE VERIFIED: `calendar-auth` token minted; `connect()` + `list_events` read the real API (2026-06-03)

### ▸ Checkpoint: Calendar read works — DECISION: proceed to 3b (write) or defer it (pressure-release valve) and go to briefing on read-only

## [ DEFERRED ] Slice 3b — Calendar confirmed-WRITE  ·  `feat(calendar): confirmed event creation`   [pressure-release valve — shipped read-only, write is a small follow-on]
- [ ] (source-driven) verify `events.insert` + write scope (re-auth if token lacks write scope)
- [ ] `create_event`; `:schedule <NL>` -> LLM proposes -> CLI prints -> confirm `y` -> deterministic create (never silent)
- [ ] Verify: unit (create called ONLY after confirm gate; `n` leaves calendar untouched); manual; ruff clean

## [x] Slice 4 — Daily briefing  ·  `feat(briefing): on-demand daily briefing (calendar + goals + knowledge)`
- [x] `briefing.py` — deterministic assemble(today's calendar + active goals + Phase-1 knowledge digest) -> LLM phrases; sourced
- [x] `:brief`/`:briefing` command (emits signal); empty sections handled; UTF-8 stdout hardening
- [x] Verify: unit (block has all three; LLM fed only that data; empty handling); manual `:brief` live; 147 green; ruff clean

### ▸ Checkpoint: Phase 2 feature-complete (signals, memory, goals, calendar-read, briefing; 3b deferred) → `/test` → `/review` → `/code-simplify` → `/ship`
