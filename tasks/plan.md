# Plan: Jarvis — Phase 5 (Proactivity / Jarvis Core)

Source-of-truth: `SPEC.md` (5a active; 5b/5c north star) + `CLAUDE.md` + `docs/Jarvis_Core_Spec.md`
(Stages 4–7; §7.2/§7.4/§7.5; §5.3/§5.5; **§8 the objective constraint**). Run as **three sub-phases,
each its own /spec → /ship cycle**: build + ship **5a**, then spec 5b, then 5c. One vertical slice per
commit. Phases 0–4 shipped (plans in git history).

**THE law (binds all of 5a–5c):** usefulness, never engagement. Deterministic-first: triggers, context
assembly, ranking features, confidence + feedback math are CODE; the LLM only synthesizes (grounded) and
phrases. Everything local; everything inspectable; nothing about my behavior leaves the machine.

```
5a  REFLECTION + USER MODEL  (this build — the understanding the ranker will score against)
    Slice 1  Reflection trigger     §7.4 deterministic accumulation of per-kind signal importance
    Slice 2  Context + synthesis     deterministic aggregation + memory retrieval -> grounded LLM insights
    Slice 3  User model              inspectable UserModel; deterministic merge (confidence rise/decay)
        |  >>> ship 5a, then spec 5b <<<
5b  ENGINE        candidate triggers (code) -> explainable usefulness ranking (§7.2) -> top-K to the feed
5c  FEEDBACK      Outcome -> model/ranker update (§7.5) + explore/exploit (§7.3) + scheduler + auto-briefing
```

Order: 5a Slice 1 (trigger) → 2 (synthesis) → 3 (user model). Slices 2–3 depend on 1; 3 consumes 2's
insights. 5b depends on the user model (3); 5c closes the loop on 5b.

Dependency graph:
- Slice 1 (trigger) ← the existing signal log; pure deterministic.
- Slice 2 (context+synthesis) ← Slice 1 (fires) + the existing MemoryStore/§7.1 + signal log.
- Slice 3 (user model) ← Slice 2 (insights feed the model) + the Phase-2 goals store.

---

## Task List — 5a (active)

### Slice 1 — Reflection trigger (§7.4, deterministic)  [review-hardened]
**Acceptance:**
- [ ] `proactivity/trigger_weights.py`: per-kind **trigger FUEL** weights (user-value, not attention:
  goal_done/explicit remember/preference high, routine command low) + an **attention denylist**
  (`{suggestion_shown, item_dwell, ...}`) where `trigger_fuel(kind)` returns **0.0**. Fuel ≠ feedback reward.
- [ ] `proactivity/trigger.py`: `accumulated_fuel(signals_since)` + `should_reflect(accumulated, threshold)`;
  `REFLECTION_THRESHOLD`/fuel weights in `config`.
- [ ] `stores`: reflection-state get/save (last processed **`seq`** + display `last_reflection_at`) and
  `get_signals_since(after_seq)` on the `StructuredStore` interface (raw SQL in sqlite). Baseline = seq.
- [ ] `tests/test_boundaries.py`: proactivity deterministic modules import no LLM.

**Verification:** `test_reflection_trigger.py` — fuel is deterministic; **denylisted kinds -> 0.0**;
`accumulated_fuel` sums only signals after the seq baseline; `should_reflect` fires at the threshold;
baseline advances so consumed signals don't recount. No LLM. `test_proactivity_store.py` — state +
`get_signals_since` round-trip. **Files:** `proactivity/{__init__,trigger_weights,trigger}.py`,
`stores/*`, `config.py`, `tests/test_boundaries.py`, tests. **Scope:** M.
**Commit:** `feat(proactivity): deterministic reflection trigger (§7.4) over the signal log`

### Slice 2 — Reflection context + grounded synthesis (Stage 4)
**Source-driven first:** re-confirm the Ollama JSON-schema generation path + `MemoryStore.retrieve` /
signal-log query shapes.
**Acceptance:**
- [ ] `proactivity/context.py`: `build_context(signals_since, memories, goals, *, now)` — **deterministic**:
  **rhythms/cadence/modality/time-of-day from the signal log** (NOT topics — the log has none) +
  **interests/preferences grounding from the explicit memories + goals**; takes an **injected `now`** and
  an **already-retrieved** memory list (offline tests don't touch live Chroma); runs the block through
  `jarvis/redact.py`; returns the EXACT text the LLM may see.
- [ ] `proactivity/reflect.py`: `synthesize(context, llm) -> list[Insight]` — JSON-schema-constrained;
  `Insight{kind: interest|rhythm|preference|observation, content, topic?, weight?, links:[id]}`.
  `reflect(...)` writes each valid one as `MemoryRecord(type=reflection, source=reflection, links=sources)`.
  **Grounded iff** links non-empty AND every id resolves to a context record; ungrounded/malformed → dropped;
  content must be an abstraction (no verbatim source reuse).
- [ ] `service.reflect()` (trigger-or-force) emits a **metadata-only** signal (counts/forced only);
  `__main__` `reflect` subcommand. Baseline advances only on a persisted, successful reflection.

**Verification:** `test_reflection_context.py` — aggregates deterministically with a fixed `now` + injected
memories; the prompt == instruction + the assembled block, byte-for-byte (grounding, like the briefing test).
`test_reflect.py` — fake LLM: valid insights → linked `reflection` memories; an ungrounded AND a malformed
item are dropped; no verbatim source reuse; the reflect signal carries no insight text. Integration-gated live.
**Files:** `proactivity/{context,reflect}.py`, `service.py`, `__main__.py`, tests. **Scope:** L.
**Commit:** `feat(proactivity): grounded reflection synthesis over retrieved memories + signal aggregates`

### Slice 3 — User model (Stage 5, inspectable + controllable)  [review-hardened]
**Acceptance:**
- [ ] `proactivity/user_model.py`: `UserModel` (§5.3) value objects; a **pure** `confidence_after(current,
  observation) -> float` (re-confirm `clamp(c+α(1−c))`, contradiction `clamp(c−γc)`; α,γ in config;
  "contradiction" = suppress_topic / less_like_this / opposite-signed insight on the same key); `merge`
  delegates to it. **Pure-frequency observations do NOT raise a ranker-facing `Interest.weight`** — only
  goal-linked/confirmed topics do (else recorded as a descriptive observation). Explicit goal/preference wins.
- [ ] `stores`: user_model get/save (materialized); **goals are read live from the Phase-2 store only**
  (reflection never writes a goal); reflection updates the derived parts; reflection records marked inferred.
- [ ] Control surface: `service.user_model()` / `forget(id)` / `reset_user_model()`; `cli` `:profile` /
  `:why` (insight provenance) / `:forget` / `:reflect`.

**Verification:** `test_user_model.py` — `confidence_after` exact values + clamps + monotonic + order-
independent; same interest twice → up, contradiction → down; **pure frequency yields an observation, not an
amplifiable interest weight**; explicit goal reflected; reproducible. `:profile`/`:why` inspectable; `:forget`
+ reset work. **Files:** `proactivity/user_model.py`, `proactivity/reflect.py`, `stores/*`, `service.py`,
`cli.py`, `config.py`, `tests/test_user_model.py`. **Scope:** M.
**Commit:** `feat(proactivity): inspectable user model materialized by reflection (confidence rise/decay)`

### ▸ Checkpoint: 5a complete (Jarvis knows the user)
- [ ] Reflection runs (trigger/on-demand) → grounded insight memories; an inspectable user model updates
  from signals/reflections/goals with confidence rise/decay; deterministic + local; LLM only synthesizes,
  grounded + validated. → `/test` → **multi-lens adversarial review (incl. objective-drift lens)** →
  `/code-simplify` → `/ship` → record learnings → **then spec 5b**.

## North star — 5b / 5c (specified, built next as their own cycles)

### 5b — Engine (candidate generation + ranking)
- Deterministic candidate triggers (code): watched-stock move, calendar event approaching, goal deadline
  near, recurring pattern, project-relevant news, budget threshold → a wide candidate pool (the LLM may
  phrase a candidate, never invent the trigger).
- **Explainable usefulness ranking** (§7.2): `β_goal·goal_relevance + β_urgency·urgency +
  β_interest·interest_match + β_timing·timing_fit + β_novelty·novelty − β_fatigue·fatigue`, hand-weighted
  linear; surface top‑K (cap ~3/window); each card answers **"why am I seeing this?"** (the feature
  contributions ARE the explanation). Push `Suggestion` cards to the Phase-3 feed (`post_card`).

### 5c — Feedback loop + explore/exploit + scheduler
- `Outcome` (acted/dismissed/ignored/more|less, §5.5) → **deterministic** §7.5 updates to user-model
  confidence + ranker β-weights; **measurably shifts** future ranking. `shown`/`dwell` is NEVER a positive
  reward (the objective is usefulness).
- **Explore/exploit** (§7.3): ε-exploration of an out-of-profile candidate, ε decays as model confidence
  rises. Frequency cap + fatigue + an off-switch + tuning (suppress_topic preference).
- **Scheduler** (Core §9 Heartbeat): run reflection on its threshold + the candidate→rank pass on
  schedule/events, push to the feed; **auto-fire the daily briefing** (deferred from Phase 2).
- **A test proves the objective is usefulness, not engagement.**

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Objective drifts toward engagement/manipulation | CRITICAL (project purpose) | Usefulness-only feedback label; shown/dwell never rewards; explainable ranking; freq-cap; off-switch; a dedicated adversarial review lens |
| LLM free-associates an ungrounded "insight" | High | Synthesis sees ONLY the deterministic context; insights must link to sources; ungrounded rejected; grounding test |
| User model becomes an opaque black box | High | Materialized + inspectable (`:profile`); deterministic confidence math; explicit goals/prefs win |
| Reflection over-fires (spammy/expensive) | Med | Deterministic §7.4 threshold; baseline resets; on-demand for tests; reflection is a Brain job |
| Behavioral data leaks | High | All local; signal log metadata-only; no cloud; nothing about behavior leaves the machine |
| Ranker complexity balloons | Med | Hand-weighted linear first (§7.2); ML lib only when labeled outcomes exist (§11); 5b/5c separate cycles |
| Phase 5 sprawls (it's the biggest phase) | High | Three sub-phases, each spec→ship; 5a (understanding) ships before 5b (acting) |

## Open Questions — recommendations (confirm)
- Reflection-trigger fuel = accumulated per-kind **signal** importance (+ memory importance); threshold +
  weights in config. User model = materialized row + live goals. Importance = deterministic per-kind
  heuristic. All recommended; the binding constraint (usefulness-not-engagement) is not negotiable.

## Parallelization
- Slice 1 (trigger) is independent (pure). Slices 2–3 serialize (3 consumes 2). 5b waits on the user
  model (5a/3); 5c closes the loop on 5b. Sub-phases ship in order: 5a → 5b → 5c.
