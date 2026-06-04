# Phase 5b — TODO (Proactivity Engine: candidate generation + usefulness ranking)

Tracking list for `/build`. One vertical slice per commit. Full detail in `tasks/plan.md`.
**THE law: usefulness, never engagement (Core §8).** Deterministic-first — generation, features,
ranking, selection, and the "why" are CODE; the LLM only phrases. Collector queries use public
watchlist terms only; nothing private leaves the machine; the signal log stays metadata-only.
Run as 5a → 5b → 5c (each its own spec→ship). 5a shipped (`d08b03b`). **5c is NOT in this build.**

Design spine: generators + ranker are PURE functions of an injected `EngineState`; only `suggest.py`
does I/O. Abstention is the default; the frequency cap is structural.

---

## [x] Slice 1 — Candidate model + registry + owned-data generators  ·  `feat(proactivity): candidate generation over owned data (goals, budget, recurring, calendar)` (cc02a35)
- [x] `proactivity/candidate.py` — `Provenance` + `Candidate` + `EngineState` + `CandidateGenerator` Protocol
- [x] `proactivity/generators.py` — owned generators (pure `(state)->[Candidate]`): `goal_deadline`, `stale_goal` (created_at+progress proxy; no Goal.updated_at), `budget_threshold`, `recurring_bill_due` (next = last_txn + cadence; Recurring has no due date), `event_prep` (next timed event in horizon); `GENERATORS` registry + `generate_all` (union + dedup by `entity_key`)
- [x] `config` — urgency_horizon_hours, stale_goal_days, budget_near_fraction, recurring_horizon_days
- [x] Verify: `test_candidate_generators.py` (10 tests) — each fires + abstains; provenance reason/source_ids non-empty; dedup by entity_key; purity (no facade/HTTP/LLM imports). 294 passed, ruff clean

## [x] Slice 2 — Watchlist + collector generators  ·  `feat(proactivity): user-owned public watchlist and collector candidate generators (market/news/yc)` (869cb95)
- [x] `stores` — `Watch` + `watchlist(kind,value)` table + add/get/remove CRUD (idempotent; raw SQL in sqlite)
- [x] `service` — `add_watch` (symbols upper-cased) / `watchlist` / `remove_watch`, metadata-only signals; `cli :watch add|list|rm`
- [x] `proactivity` — `Fetched(source,term,item)` + `Candidate.topics` + `EngineState.connector_items`; collector generators `market_move`/`watched_news`/`yc_launch` (pure over items); `collector_queries` pure (connector,term) builder
- [x] `config` — `market_move_pct`
- [x] Verify: `test_watchlist_store.py` round-trip; collector generator fire/abstain; **collector_queries emits only public watch terms**; facade upper-case + metadata-only. 299 passed, ruff clean

## [ ] Slice 3 — Features + ranker + gate (§7.2)  ·  `feat(proactivity): explainable usefulness ranking with abstention and a structural frequency cap`
- [ ] `proactivity/features.py` — calibrated [0,1] monotone, PURE (no LLM/httpx/attention): `goal_relevance`, `urgency`, `interest_match` (max goal-linked `Interest.weight`; 0 for pure-freq), `timing_fit` (rhythms + config quiet-hours; no UserModel.dnd), `novelty`, `recent_interruption_penalty`
- [ ] `proactivity/rank.py` — `usefulness`=Σβ·f (absolute, NO min-max) + `contributions`; `select` = abstain @ `usefulness_threshold` → DND gate → entity cooldown → per-category cap → global cap → top-K
- [ ] `config` — β weights, `usefulness_threshold`, caps/window, `entity_cooldown`, `urgency_horizon`, `stale_goal_days`, `novelty_lambda`, `quiet_hours_*`, `proactivity_enabled`
- [ ] Verify: `test_proactivity_features.py` + `test_rank.py` — exact sum; **§8 guards each a test** (no attention feature; interest_match=0 pure-freq; weak pool→[]; structural cap bounds volume; cooldown/cap/DND; top-K order); boundary: features/rank/candidate import no LLM + no httpx

## [ ] Slice 4 — Engine + persistence + phrasing + wiring  ·  `feat(proactivity): suggestion engine - generate, rank, phrase, persist, post to the feed`
- [ ] `proactivity/phrase.py` — LLM phrases card body only (the only 5b model call)
- [ ] `proactivity/suggest.py` — engine: gather `EngineState` (connector fetch w/ watchlist terms only) → generate_all → select → phrase → persist `Suggestion` → `[Card]`; abstain → `[]`
- [ ] `stores` — `save_suggestion` + `get_recent_suggestions`; `suggestions` table (§5.5)
- [ ] `service.py` — `suggestions()` + `add/list/remove_watch`; metadata-only `suggest` + `suggestion_shown` signals (0 fuel)
- [ ] `ui/feed.py` `Card.why` + `ui/controller.show_suggestions`; `cli`/`__main__` `:suggest` + `suggest` subcommand
- [ ] Verify: `test_suggest_engine.py` (fake LLM → cards w/ deterministic why resolving to real ids; Suggestion persisted; metadata-only signals; abstention message) + facade/controller tests; `pytest -q` offline green; live phrasing/collectors integration-gated

### ▸ Checkpoint: 5b feature-complete → `/test` → multi-lens review (incl. objective-drift lens, vs a real ranker) → fix → `/code-simplify` → `/ship` (push) → learnings in DECISIONS → THEN spec 5c.

## [ NORTH STAR / next cycle ] 5c — Feedback + scheduler
- `Outcome` → value-corroborated reward (acted-AND-good-outcome / explicit helpful; `acted` alone non-positive; reward by magnitude not count) → user model + β weights (§7.5); holdout value metric (drift alarm); explore/exploit (§7.3, pessimistic cold-start prior, ε decays, never raises volume); dismissal → exponential-backoff cooldown; scheduler (Heartbeat) → once-daily digest + event-triggered real-time; auto-briefing. A test proves the objective is usefulness, not engagement.
