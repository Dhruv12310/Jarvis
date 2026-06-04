# Phase 5 — TODO (5a active: Reflection + User Model)

Tracking list for `/build`. One vertical slice per commit. Full detail in `tasks/plan.md`.
**THE law: usefulness, never engagement (Core §8).** Deterministic-first — triggers, context, confidence
+ feedback math are CODE; the LLM only synthesizes (grounded) and phrases. All local; inspectable;
nothing about my behavior leaves the machine. Run as 5a → 5b → 5c (each its own spec→ship).
(Phases 0–4 shipped; todos in git history.)

---

## [x] Slice 1 — Reflection trigger (§7.4)  ·  `feat(proactivity): deterministic reflection trigger (§7.4) over the signal log`
- [x] `proactivity/trigger_weights.py` — per-kind FUEL weights + attention DENYLIST(->0.0); fuel != reward
- [x] `proactivity/trigger.py` — `accumulated_fuel(since)` + `should_reflect(...)`; `REFLECTION_THRESHOLD` in config
- [x] `stores` — `get_signals_since(seq)`/`latest_signal_seq` + `ReflectionState` (last seq) get/save; boundary guard: proactivity math imports no LLM
- [x] Verify: `test_reflection_trigger.py` (fuel + denylist->0.0 + accumulation + threshold, no LLM); `test_proactivity_store.py` (window + state round-trip)

## [x] Slice 2 — Reflection context + grounded synthesis (Stage 4)  ·  `feat(proactivity): grounded reflection synthesis over retrieved memories + signal aggregates`
- [x] (source-driven) confirmed Ollama JSON-schema generation + memory/signal shapes
- [x] `proactivity/context.py` — `build_context(signals_since, memories, goals, *, now)`: DETERMINISTIC (rhythms/modality/time-of-day from signals; interests grounding from explicit memories+goals); injected now+memories; redacted
- [x] `proactivity/reflect.py` — `synthesize` JSON-constrained → validated typed `Insight`s; grounded iff links resolve; malformed/ungrounded/verbatim dropped; `reflect()` writes `MemoryRecord(type=reflection, links)`
- [x] `service.reflect()` (trigger-gate or force; metadata-only signal); `__main__` + `:reflect`
- [x] Verify: `test_reflection_context.py` (byte-for-byte grounding); `test_reflect.py` (fake LLM → linked memories; ungrounded/malformed/verbatim dropped); facade reflect tests; integration-gated live

## [x] Slice 3 — User model (Stage 5, inspectable + controllable)  ·  `feat(proactivity): inspectable user model materialized by reflection (confidence rise/decay)`
- [x] `proactivity/user_model.py` — `UserModel` (§5.3); pure `confidence_after` (rise/decay, pinned); pure-frequency NEVER raises an amplifiable weight (Core §8); suppress_interest; to/from_dict
- [x] `stores` — user_model get/save/clear; `MemoryStore.forget` + `VectorStore.delete`; reflection merges into the model
- [x] `service.user_model()/forget/reset_user_model`; `cli` `:profile`(+reset) / `:why` / `:forget` / `:reflect`
- [x] Verify: `test_user_model.py` (confidence_after exact; goal-linked-amplifies-but-frequency-doesn't; reconfirm up; suppress decays; round-trip); facade inspect/forget/reset; `:profile`/`:why` smoke

### ▸ Checkpoint: 5a SHIPPED. 284 green, ruff clean. 3-lens review (code + privacy + objective-drift) done; 4 findings fixed (lost-signal window, suppress_topic autonomy lever, self-loop denylist, synthesis-failure retry) + guard tests. Pushed (d08b03b). Learnings in DECISIONS (Phase 5a + D23). → THEN spec 5b.

## [ NORTH STAR / next cycles ] 5b — Engine ; 5c — Feedback + scheduler
- 5b: deterministic candidate triggers → explainable usefulness ranking (§7.2) → top-K cards to the feed; every card answers "why am I seeing this?"
- 5c: `Outcome` → §7.5 model/ranker update (shown/dwell NEVER rewards) + explore/exploit (§7.3) + freq-cap/off-switch + scheduler + auto-briefing; a test proves the objective is usefulness, not engagement
