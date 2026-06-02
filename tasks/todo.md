# Phase 2 — TODO

Tracking list for `/build`. One vertical slice per commit. Full detail in `tasks/plan.md`.
Deterministic-first: LLM only phrases. **Signal capture goes in FIRST (non-negotiable).**

---

## [ ] Slice 1a — Signal capture (turn it ON first)  ·  `feat(signals): append-only signal capture on every interaction`
- [ ] `signals/event.py` `SignalEvent(id, ts, kind, payload, session_id)` (Core §5.4)
- [ ] `StructuredStore` += `save_signal`/`get_signals`; `signals` append-only table (raw SQL in sqlite_store)
- [ ] `signals/log.py` `SignalLog.emit` (per-session id; swallow-on-failure, never breaks a turn)
- [ ] `cli.py` — every turn (question, each `:` command, briefing) emits a SignalEvent; `:signals` inspector
- [ ] Verify: unit (log grows, shape, forced failure not propagated); manual `:signals`; ruff clean

### ▸ Checkpoint: Logging is ON — review before memory

## [ ] Slice 1b — Memory store + :note migration  ·  `feat(memory): typed MemoryRecord store with recency+importance+relevance retrieval`
- [ ] (source-driven) verify Chroma cosine collection + `upsert` on installed chromadb
- [ ] `vector.py`/`chroma_store.py` += `upsert` (D3) + cosine `space` (D1)
- [ ] `memory/record.py` `MemoryRecord` (§5.1); `memory/store.py` `MemoryStore.save` + `.retrieve` (§7.1: recency+importance+relevance, normalized top-K, bump last_accessed)
- [ ] importance heuristic; memory population EXPLICIT-only
- [ ] MIGRATION: existing notes -> MemoryRecords (no orphans); retire notes table; `:note`/`:recall` via MemoryStore (behavior preserved)
- [ ] Verify: unit (round-trip, §7.1 ranking, last_accessed bump, migration no-loss); `:note`/`:recall` intact; ruff clean

### ▸ Checkpoint: Memory real

## [ ] Slice 2 — Goals CRUD  ·  `feat(goals): goal/project CRUD via the structured store`
- [ ] `Goal(id, description, status, progress, priority, deadline, created_at)`; StructuredStore save/get/update_goal; `goals` table
- [ ] `cli.py` — `:goal add <text>`, `:goals`, `:goal done <id>` (each emits a signal)
- [ ] Verify: unit (CRUD + persistence); ruff clean

## [ ] Slice 3a — Calendar READ (OAuth)  ·  `feat(calendar): read Google Calendar via OAuth (read-only)`   [the risk; read first]
- [ ] (source-driven) verify Google OAuth InstalledApp flow + Calendar v3 `events.list` + event resource shape
- [ ] pyproject += 3 google libs; approved deps updated; boundary guard: google libs only under `calendar/`
- [ ] config: `google_credentials_path`/`google_token_path` (./data/, git-ignored)
- [ ] `calendar/oauth.py` (flow + token persist/refresh); `calendar/client.py` `list_events` -> CalendarEvent
- [ ] `__main__.py` `calendar-auth`; `cli.py` `:cal`/`:agenda`; docs: step-by-step Google Cloud setup (Desktop client, consent TESTING + own account, credentials.json -> ./data/)
- [ ] Verify: unit (fake google service normalization); integration skips w/o token; manual `calendar-auth` + `:cal`; ruff clean

### ▸ Checkpoint: Calendar read works — DECISION: proceed to 3b (write) or defer it (pressure-release valve) and go to briefing on read-only

## [ ] Slice 3b — Calendar confirmed-WRITE  ·  `feat(calendar): confirmed event creation`   [DEFERRABLE]
- [ ] (source-driven) verify `events.insert` + write scope (re-auth if token lacks write scope)
- [ ] `create_event`; `:schedule <NL>` -> LLM proposes -> CLI prints -> confirm `y` -> deterministic create (never silent)
- [ ] Verify: unit (create called ONLY after confirm gate; `n` leaves calendar untouched); manual; ruff clean

## [ ] Slice 4 — Daily briefing  ·  `feat(briefing): on-demand daily briefing (calendar + goals + knowledge digest)`
- [ ] `briefing.py` — deterministic assemble(today's calendar + active goals + Phase-1 knowledge digest) -> LLM phrases; sourced
- [ ] `briefing` command (emits signal); empty sections handled
- [ ] Verify: unit (assembled block has all three; LLM fed only that data; empty handling); manual `briefing`; ruff clean

### ▸ Checkpoint: Phase 2 DoD met (signals logging, memory, goals, calendar, briefing) → `/test` → `/review` → `/code-simplify` → `/ship`
