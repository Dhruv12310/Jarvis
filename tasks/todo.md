# Phase 5 — TODO (5a active: Reflection + User Model)

Tracking list for `/build`. One vertical slice per commit. Full detail in `tasks/plan.md`.
**THE law: usefulness, never engagement (Core §8).** Deterministic-first — triggers, context, confidence
+ feedback math are CODE; the LLM only synthesizes (grounded) and phrases. All local; inspectable;
nothing about my behavior leaves the machine. Run as 5a → 5b → 5c (each its own spec→ship).
(Phases 0–4 shipped; todos in git history.)

---

## [ ] Slice 1 — Reflection trigger (§7.4)  ·  `feat(proactivity): deterministic reflection trigger (§7.4) over the signal log`
- [ ] `proactivity/importance.py` — deterministic per-kind `SignalEvent` importance (from genuine significance, NOT attention/dwell)
- [ ] `proactivity/trigger.py` — `accumulated_importance(since)` + `should_reflect(...)`; `REFLECTION_THRESHOLD` in config
- [ ] `stores` — reflection-state get/save (`last_reflection_at` + baseline) so "since last reflection" is durable
- [ ] Verify: `test_reflection_trigger.py` (deterministic importance + accumulation + threshold fire/reset, no LLM); `test_proactivity_store.py` (state round-trip)

## [ ] Slice 2 — Reflection context + grounded synthesis (Stage 4)  ·  `feat(proactivity): grounded reflection synthesis over retrieved memories + signal aggregates`
- [ ] (source-driven) re-confirm Ollama JSON-schema generation + `MemoryStore.retrieve` / signal-log shapes
- [ ] `proactivity/context.py` — `build_context(signals_since, memory, goals)`: DETERMINISTIC aggregation (kind counts, topics, time-of-day, modality) + §7.1 memory retrieval → the exact block the LLM may see
- [ ] `proactivity/reflect.py` — `synthesize(context, llm)` JSON-constrained → typed `Insight`s; `reflect()` writes `MemoryRecord(type=reflection, links=sources)`; ungrounded insight rejected
- [ ] `service.reflect()` (trigger-or-force, metadata-only signal); `__main__` `reflect` subcommand
- [ ] Verify: `test_reflection_context.py` (deterministic aggregates; prompt = only the assembled block, grounding); `test_reflect.py` (fake LLM → linked reflection memories; ungrounded rejected); integration-gated live synthesis

## [ ] Slice 3 — User model (Stage 5, inspectable)  ·  `feat(proactivity): inspectable user model materialized by reflection (confidence rise/decay)`
- [ ] `proactivity/user_model.py` — `UserModel` (§5.3) value objects; `merge(insight)` deterministic confidence (RISES on re-confirm, DECAYS on contradiction); explicit goal/preference wins
- [ ] `stores` — user_model get/save (materialized); goals merged live from the Phase-2 store; reflection updates the model
- [ ] `service.user_model()`; `cli` `:reflect` / `:profile`
- [ ] Verify: `test_user_model.py` (same interest twice → up; contradiction → decay; explicit goal reflected; reproducible); `:profile` inspectable

### ▸ Checkpoint: 5a complete → `/test` → multi-lens adversarial review (incl. objective-drift lens) → `/code-simplify` → `/ship` → record learnings → THEN spec 5b

## [ NORTH STAR / next cycles ] 5b — Engine ; 5c — Feedback + scheduler
- 5b: deterministic candidate triggers → explainable usefulness ranking (§7.2) → top-K cards to the feed; every card answers "why am I seeing this?"
- 5c: `Outcome` → §7.5 model/ranker update (shown/dwell NEVER rewards) + explore/exploit (§7.3) + freq-cap/off-switch + scheduler + auto-briefing; a test proves the objective is usefulness, not engagement
