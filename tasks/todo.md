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

## [x] Slice 3 — Features + ranker + gate (§7.2)  ·  `feat(proactivity): explainable usefulness ranking with abstention and a structural frequency cap` (5041874)
- [x] `proactivity/features.py` — calibrated [0,1] monotone, PURE: `goal_relevance`, `urgency`, `interest_match` (max goal-linked `Interest.weight`; 0 for pure-freq), `timing_fit` (config quiet-hours), `novelty`, `recent_interruption_penalty`
- [x] `proactivity/rank.py` — `usefulness`=Σβ·f (absolute, NO min-max) + `contributions`; `select` = abstain @ `usefulness_threshold` → DND gate → entity cooldown → per-category cap → global cap → top-K
- [x] `config` — β weights, `usefulness_threshold`, caps/window, `entity_cooldown`, `novelty_lambda`, `quiet_hours_*`, `proactivity_enabled`; `EngineState` += user_model + recent_suggestions
- [x] Verify: `test_proactivity_features.py` + `test_rank.py` — exact sum; §8 guards each a test (no attention feature; interest_match=0 pure-freq; weak pool→[]; structural cap bounds volume; cooldown/cap/DND; top-K order); boundary: features/rank/candidate import no LLM. 314 passed, ruff clean

## [x] Slice 4 — Engine + persistence + phrasing + wiring  ·  `feat(proactivity): suggestion engine - generate, rank, phrase, persist, post to the feed`
- [x] `proactivity/phrase.py` — LLM phrases card body only (the only 5b model call; grounded on reason+payload)
- [x] `proactivity/suggest.py` — `build(state, chat, now)`: generate_all → select → phrase → `Suggestion[]`; deterministic `_why`; abstain → `[]`
- [x] `stores` — `Suggestion` (§5.5 +entity_key/why/source_ids) + `suggestions` table + `save_suggestion`/`get_recent_suggestions`
- [x] `service.py` — `suggestions(now=None)` gathers `EngineState` (collector fetch w/ watchlist terms only) + persists + metadata-only `suggest`/`suggestion_shown`; connectors wired via `build_service`
- [x] `ui/feed.py` `Card.why` + `ui/controller.show_suggestions`; `cli :suggest`; `python -m jarvis suggest`
- [x] Verify: `test_suggest_engine.py` (deterministic why → real ids; abstention) + facade persistence/metadata-only test

### ▸ Checkpoint: 5b feature-complete → `/test` → multi-lens review (incl. objective-drift lens, vs a real ranker) → fix → `/code-simplify` → `/ship` (push) → learnings in DECISIONS → THEN spec 5c.

## [ NORTH STAR / next cycle ] 5c — Feedback + scheduler
- `Outcome` → value-corroborated reward (acted-AND-good-outcome / explicit helpful; `acted` alone non-positive; reward by magnitude not count) → user model + β weights (§7.5); holdout value metric (drift alarm); explore/exploit (§7.3, pessimistic cold-start prior, ε decays, never raises volume); dismissal → exponential-backoff cooldown; scheduler (Heartbeat) → once-daily digest + event-triggered real-time; auto-briefing. A test proves the objective is usefulness, not engagement.
