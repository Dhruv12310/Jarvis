# Spec: Jarvis — Phase 5 (Proactivity / Jarvis Core)

> Per-phase spec for the **active** phase. Phases 0–4 are shipped; their specs live in `docs/specs/`
> and git history. Phase 5 is run as **three sub-phases — 5a / 5b / 5c — each its own /spec → /ship
> cycle**. **THIS spec's active build target is 5a (Reflection + User Model).** 5b (candidate
> generation + ranking) and 5c (feedback loop + explore/exploit + scheduler) are specified here as the
> binding north star; they get their own focused spec when 5a ships.
>
> Design source-of-truth: `CLAUDE.md` (invariants) and **`docs/Jarvis_Core_Spec.md` IN FULL** — this
> phase implements Core Stages 4–7. Read §5.3 (UserModel), §5.5 (Suggestion/Outcome), §6 (the pipeline),
> §7.2 (ranking), §7.3 (explore/exploit), §7.4 (reflection trigger), §7.5 (feedback), and **§8 (the
> objective constraint — the heart of this phase)**. Phase 0–4 learnings: `docs/DECISIONS.md`. The
> accumulated `SignalEvent` log (live since Phase 2, now across CLI/GUI/voice/finance) is the fuel.

## Objective

Jarvis becomes **proactive**: it reflects on what it has observed about me, builds an inspectable model
of my goals and patterns, and surfaces genuinely useful suggestions to the **desktop Jarvis feed**
(Phase 3) at the right moments — learning from whether they actually helped. Runs locally; delivers to
the desktop feed (mobile is Phase 6). Finishing Phase 5 means the **desktop Jarvis is done.**

**5a (this build):** turn the signal log into knowing-the-user. **Reflection** (Stage 4) synthesizes the
accumulated signals + memories into grounded insight memories; the **User Model** (Stage 5) is the
standing, inspectable profile (interests, rhythms, goals, preferences, DND) the ranker will later score
against. No suggestions are surfaced yet — 5a builds the *understanding* the engine (5b) ranks with.

## THE ethical constraint (non-negotiable — the heart of this phase, Core §8)

**The ranker's learning target is USEFULNESS — did a suggestion save me time, advance a goal, or
prevent a miss — NEVER engagement, time-on-app, click-through-as-an-end, or notification volume.** This
is *Instagram's mechanism (a two-stage recommender), not its objective (capturing attention).* It binds
the WHOLE phase even though the ranker is 5b/5c, because the choices that cause drift are made early —
in what the user model encodes and what the feedback signal will reward. Concretely, enforced across
5a–5c:
- The feedback label measures **genuine value** (acted on AND a good outcome / explicitly marked
  helpful) — **never** views, dwell, or attention captured. A `suggestion_shown`/`item_dwell` signal is
  **never** a positive reward.
- Suggestions are **frequency-capped** and never spammy (cap ~3 per window, fatigue penalty).
- Every suggestion can answer **"why am I seeing this?"** — ranking is **explainable code**, not an
  opaque LLM verdict.
- I can always **dismiss, tune, suppress a topic, turn proactivity down/off**. The system serves me, not
  the reverse. **If a choice would raise engagement at the expense of usefulness or my autonomy, it is
  the wrong choice** — and a dedicated adversarial review lens exists to catch exactly that fork.
- 5a embodiment: the user model is **inspectable** (`:profile`) and editable-by-consequence (my explicit
  goals/preferences win); reflection is **grounded** on deterministically-retrieved data, never free
  association.

## Design hardening from the adversarial review (BINDING — folded in before building)

The multi-lens review (objective-drift, Core-fidelity, privacy, buildability) surfaced that the
constraint above was prose, not yet enforcement, and that one input was assumed richer than it is.
Resolutions, all binding on 5a:

1. **The signal log has NO topics** (metadata-only by Phase 2–4 design). So reflection draws **rhythms /
   cadence / modality / time-of-day from the signal log**, and **interests / preferences from the
   explicit `MemoryRecord` corpus + goals** — NOT "topics from signal payloads" (that field doesn't
   exist). A bounded capability-domain enum tag on signals (e.g. `finance|calendar|knowledge|goals`,
   derived from the capability, never from query text) is a possible future enrichment but is an **Ask
   First** trust-boundary change — not assumed here.
2. **Frequency is never interest-to-amplify.** Pure-frequency behavior becomes a *descriptive
   observation*; it must **NOT** raise a ranker-facing `Interest.weight`. Only **goal-linked or
   explicitly-confirmed** topics raise amplifiable interest weight. A `suppress_topic`/`less_like_this`
   can drive weight DOWN even when frequency is high. (Guards against amplifying a compulsion.)
3. **Attention-derived signal kinds are denylisted in code.** `{suggestion_shown, item_dwell, ...}` →
   `trigger_fuel(kind)` returns **0.0** (a test asserts it); `dwell_ms` must never enter a payload
   reflection reads. The trigger-**fuel** weight and the (5c) feedback **reward** label are two
   different numbers in two different modules — never reuse one as the other.
4. **`acted` alone is never a positive reward (5c, stated now).** The positive label requires
   value-corroboration (explicit "helpful" / a goal-progress outcome); `shown`/`dwell` is never
   positive. A 5c test must prove acted-without-value yields non-positive weight movement.
5. **Confidence is a pure, pinned function.** `confidence_after(current, observation) -> float`:
   re-confirm `c' = clamp(c + α·(1−c))` (saturating toward 1), contradiction `c' = clamp(c − γ·c)`
   (toward 0); `α, γ` in `config`; "contradiction" = a `suppress_topic`/`less_like_this`/opposite-signed
   insight on the same key. Monotonic, reproducible, unit-tested to exact values (no LLM).
6. **Determinism:** the reflection baseline is the last-processed **`seq`** (monotonic), not a timestamp;
   add `StructuredStore.get_signals_since(after_seq)`. `build_context(..., *, now)` takes an injected
   clock and is given an **already-retrieved** memory list in offline tests (no live Chroma/clock) so the
   byte-for-byte grounding assertion is stable. Baseline advances only on a **persisted, successful**
   reflection.
7. **Grounding is validated, not assumed.** An insight is grounded iff its `links` are non-empty **and
   every id resolves to a record in the assembled context**; ungrounded → dropped. A signal-grounded
   insight (e.g. a rhythm) links a provenance token for its signal-aggregate bucket. Malformed LLM items
   are skipped-and-continue (never crash). Synthesized `reflection` content must be an **abstraction**,
   never a verbatim copy of a source memory (a test asserts no byte-for-byte reuse).
8. **Privacy + autonomy:** the assembled context is run through `jarvis/redact.py` before the LLM; the
   `reflect()` signal payload is enums/counts only (no insight text/topics); reflection records are
   marked **inferred** wherever surfaced; and 5a ships a minimal control surface (`:forget <id>`,
   user-model **reset/clear**, mark an inferred item wrong → confidence pinned low). The user model +
   reflection records are the highest-sensitivity at-rest data; any future export/sync must treat them so.
9. **Structural guard:** `proactivity/{trigger_weights,trigger,context,user_model}.py` import **no LLM**
   (a boundary test, mirroring the finance-engine guard) — the math/merge/trigger can never call a model.
10. **A `:why` provenance view** (each interest/insight → the source signals/memories that built it),
   cheap because insights already link sources — so I can catch amplification myself.

### Assumptions (correct me before I build)

1. **Phase 5 is where signals become memories.** Phase 2's "explicit-only memory" was, by its own words,
   a deferred *Stage-4/5 policy*. 5a reflection is that stage: it reads the raw `SignalEvent` log,
   **deterministically** aggregates it (counts/topics/time-of-day/modality — code, not the LLM), and the
   LLM synthesizes grounded insights that are written back as `reflection` MemoryRecords. No new plumbing
   — it consumes the existing signal log, memory store, goals, calendar, finance via the facade.
2. **Reflection trigger is deterministic (§7.4).** Each signal gets a deterministic per-kind importance
   weight; `accumulated_importance(since last reflection) ≥ REFLECTION_THRESHOLD` fires reflection. (The
   spec phrases §7.4 over "new memories"; since Phase-2 memory is explicit/sparse and the signal log is
   the continuous fuel, the trigger accumulates signal-importance, and memory-importance also counts.
   The threshold + weights are config.) Reflection is **forceable on demand** for testing/use.
3. **The LLM only synthesizes + phrases; everything else is code.** The reflection trigger, the context
   assembly (signal aggregation + memory retrieval via existing §7.1), the user-model merge + confidence
   math, and (5b/5c) the candidate triggers + ranking features + feedback updates are **deterministic**.
   The LLM does reflection synthesis (over the grounded context) and suggestion phrasing only — and its
   output is **structured + validated** (typed insight items), not a free-text verdict.
4. **The User Model is a materialized, inspectable view (§5.3).** Derived parts (interests/rhythms/
   preferences/DND) are materialized by reflection and stored; `goals` are read live from the Phase-2
   structured store. Per-item **confidence rises on re-confirmation and decays when contradicted** —
   deterministic math. Stored via `StructuredStore` (no raw SQL outside the sqlite module).
5. **Grounded, not free-associated.** The synthesis prompt receives ONLY the deterministically-assembled
   context (signal aggregates + retrieved memories + current goals) and is told to derive insights *only*
   from that data; each insight **links to its source** records. A reflection that invents a pattern with
   no support in the data is a defect.

## Trust boundary (behavioral data is the most intimate yet)

- **Reflection, the user model, ranking, and feedback all run LOCALLY.** Nothing about my behavior leaves
  the machine. The signal log, memories, and user model never cross to the cloud.
- The only model calls are **local Ollama** (reflection synthesis; later, suggestion phrasing). No cloud
  escalation / Model Router (deferred; reflection/ranking stay local — Core §9: reflection on the Brain).
- **Signal log stays metadata-only** (carried over from Phases 2–4): no raw query text, amounts, or
  merchant strings. Reflection works over those metadata + explicit memory content + structured facts.
- The user model is **inspectable and mine** — I can see and turn down everything it infers.

## Tech Stack

| Concern | Choice | Why |
|---|---|---|
| Reflection trigger / context / user-model math | pure Python (deterministic) | §7.4 + §7.2 features + confidence are code; explainable, testable, free |
| Reflection synthesis | local Ollama `LLMClient` (existing), JSON-schema-constrained | Grounded synthesis over assembled context; structured + validated output |
| Memory retrieval for context | existing `MemoryStore` (§7.1) | Reuse Phase-2 retrieval; no new plumbing |
| Signal history | existing `SignalEvent` log (StructuredStore) | The fuel since Phase 2 |
| User model / reflection state | `StructuredStore` (SQLite) | Materialized view + last-reflection state; raw SQL only in sqlite module |
| Composition | the `JarvisService` facade (Phase 3) | Adds intelligence over existing capabilities, not new plumbing |

**No new runtime deps for 5a.** (5b/5c stay hand-weighted/linear per §7.2 — no ML library yet; graduate
to logistic/GBDT only once a labeled outcome set exists, per §11.)

## Commands (5a)

```bash
python -m jarvis                 # CLI: + :reflect (force a reflection), :profile (inspect the user model)
python -m jarvis reflect         # run reflection once on demand (Brain job), then exit
pytest -q                        # offline: trigger/context/user-model math with the LLM faked
pytest -q -m integration         # live: reflection synthesis against real Ollama (gated like prior phases)
ruff check . ; ruff format --check .
```

## Project Structure (5a)

```
jarvis/
  proactivity/               # Jarvis Core: reflection + user model (5a); engine + feedback (5b/5c)
    __init__.py
    trigger_weights.py       # per-kind trigger FUEL weights + the attention denylist (dwell/shown -> 0.0)
    trigger.py               # §7.4 accumulated-fuel over signals-since-last-seq vs threshold (deterministic)
    context.py               # build_context(signals_since, memories, goals, *, now): the deterministic block
    reflect.py               # LLM synthesis over the grounded + redacted context -> validated typed Insights
    user_model.py            # UserModel (§5.3) + confidence_after() (pure) + deterministic merge
  stores/
    structured.py            # += user_model get/save; reflection-state (last seq); get_signals_since(seq)
    sqlite_store.py          # += user_model + reflection_state tables (raw SQL stays here)
  service.py                 # += reflect()/user_model()/forget(id)/reset_user_model() (inspectable+control)
  cli.py / __main__.py       # += :reflect / :profile / :why / :forget ; `reflect` subcommand
tests/
  test_reflection_trigger.py # fuel weights + denylist(->0.0) + accumulation-since-seq + threshold (no LLM)
  test_reflection_context.py # deterministic aggregation (injected now + injected memories); byte-for-byte grounding
  test_reflect.py            # fake LLM -> validated linked insights; ungrounded/malformed dropped; no verbatim; metadata-only signal
  test_user_model.py         # confidence_after exact values; re-confirm UP / contradiction DOWN; frequency does NOT raise interest weight
  test_proactivity_store.py  # user_model + reflection_state round-trip; get_signals_since
```

## Code Style (5a)

The LLM synthesizes over a code-built, grounded context; the code owns the trigger, the merge, and the math.

```python
# proactivity/user_model.py — Core §5.3. An inspectable, materialized profile.
@dataclass(frozen=True)
class Interest:   topic: str; weight: float; confidence: float; last_updated: datetime
@dataclass(frozen=True)
class Rhythm:     pattern: str; window: str; days: str; confidence: float
@dataclass(frozen=True)
class Preference: key: str; value: str; confidence: float
@dataclass(frozen=True)
class UserModel:
    interests: list[Interest]; rhythms: list[Rhythm]; goals: list  # goals read live from Phase-2 store
    preferences: list[Preference]; dnd: list; updated_at: datetime
```

```python
# proactivity/reflect.py — the LLM synthesizes ONLY over the grounded context; output is typed + validated.
#   context  = build_context(signals_since, memory_store, goals)   # DETERMINISTIC aggregation
#   insights = synthesize(context, llm)   # LLM -> [{kind: interest|rhythm|preference|observation,
#                                                    content, topic?, weight?, links:[memory_id]}] (schema)
#   for each insight: write MemoryRecord(type=reflection, source=reflection, links=sources)
#                     + user_model.merge(insight)   # DETERMINISTIC confidence update
```

```python
# proactivity/trigger.py — §7.4, deterministic.
#   importance(signal)            = WEIGHTS[signal.kind]   # per-kind, code-defined (NOT engagement-derived)
#   accumulated(since)            = sum(importance(s) for s in signals_since_last_reflection)
#   should_reflect()              = accumulated() >= REFLECTION_THRESHOLD     # config
```

Conventions (carry forward): type hints, frozen dataclasses, `ABC`/`Protocol` seams, one config location,
conventional commits (no em-dashes, no attribution), ruff clean, commit per slice. The LLM never
computes a score or invents a trigger; reflection synthesis is grounded + validated.

## Testing Strategy (5a)

- **Trigger (unit):** per-kind signal importance is deterministic; `accumulated_importance` sums correctly;
  `should_reflect` fires at the threshold and resets after a reflection. No LLM.
- **Context (unit):** `build_context` aggregates a fixture signal log deterministically (counts, topics,
  time-of-day, modality) and retrieves memories via §7.1; assert the synthesis prompt contains ONLY the
  assembled data (grounding — no smuggled context), like the briefing's byte-for-byte block test.
- **Reflect (unit):** with a **fake LLM** returning typed insights, `reflect` writes `reflection`
  MemoryRecords linked to their sources and merges each into the user model; assert an insight with no
  source link is rejected (grounding) and the LLM saw no raw private text beyond the assembled context.
- **User model (unit):** merging the same interest twice **raises** its confidence; a contradicting
  signal/insight **decays** it; an explicit goal/preference is reflected; the model is reproducible.
- **Store (unit):** user_model + reflection_state round-trip (temp SQLite).
- **Integration (`-m integration`):** real Ollama reflection synthesis over a small fixture history,
  gated like the keyed connectors / OAuth / voice.
- **Ethics (carried forward to 5b/5c, stated now):** a test will prove the ranker/feedback reward
  acted-on/helpful outcomes and **NOT** mere views/dwell/attention — the objective is usefulness.

## Boundaries

- **Always:**
  - Deterministic: the reflection trigger, context assembly, user-model merge/confidence, and (5b/5c)
    candidate triggers, ranking features, and feedback updates. The LLM only synthesizes (grounded) and
    phrases.
  - The user model is **inspectable**; reflection is **grounded** (insights link to sources); everything
    runs **locally**; the signal log stays metadata-only.
  - **(5b/5c) Usefulness, never engagement** — the feedback label and ranking features encode genuine
    value; `shown`/`dwell` is never a positive reward; suggestions are frequency-capped, explainable,
    dismissable, tunable, and can be turned off.
  - `pytest` + `ruff` before each commit; conventional commits; commit per slice.
- **Ask First:**
  - Any new dependency (5a needs none; 5b/5c stay hand-weighted/linear — an ML lib is a later, separate
    decision per §11).
  - Changing the `MemoryRecord` / `SignalEvent` / `StructuredStore` interfaces.
- **Never:**
  - Optimize for **engagement, attention, time-on-app, dwell, or notification volume**; build dark
    patterns or manipulative nudging (Core §8 — the whole point of the phase).
  - Let the LLM compute a ranking score, invent a trigger, or free-associate an insight without grounding.
  - Build the **mobile** surface (Phase 6); add new capability domains/connectors; cloud escalation /
    Model Router; financial/investment **advice** (proactive finance surfaces opted-in facts only).
  - Let anything about my behavior leave the machine.

## Success Criteria — 5a Definition of Done (testable)

1. **Reflection runs** (on the §7.4 trigger or on demand) and produces **grounded** `reflection`
   insight memories from my real signal history — each insight linked to its source records.
2. **A user model exists, is inspectable** (`:profile`), and **updates** from signals + reflections +
   my explicit goals; per-item confidence rises on re-confirmation and decays on contradiction.
3. The reflection **trigger is deterministic** (§7.4) and unit-tested; reflection synthesis is
   **grounded** (the LLM sees only the assembled context) and **validated** (typed insights).
4. **A test proves the LLM is not the judge of the model:** a boundary test asserts the proactivity
   deterministic modules import no LLM; the trigger, context aggregation, and `confidence_after` math
   are unit-tested with the LLM absent to **exact values**; synthesis output is schema-validated, an
   **ungrounded or malformed insight is dropped**, and no insight reproduces a source memory verbatim.
5. **The usefulness law is enforced in code, not prose:** a test asserts attention-derived signal kinds
   (`dwell`/`shown`) yield **0.0** trigger fuel, and that **pure-frequency behavior does NOT raise a
   ranker-facing interest weight** (only goal-linked/confirmed topics do). The `reflect()` signal is
   metadata-only (no insight text).
6. **I have control over my own model:** `:profile` shows it, `:why` shows each insight's provenance,
   `:forget <id>` deletes a reflection, and the user model can be reset/cleared.
7. Everything runs **locally**; `pytest -q` passes fully offline; reflection synthesis is
   integration-gated; `ruff` clean.

## North star — Phase 5 Definition of Done (5b + 5c, specified, built next)

- **5b — Engine:** deterministic candidate triggers (watched stock moved, calendar event approaching,
  goal deadline near, recurring pattern, project-relevant news, budget threshold) → a candidate pool;
  **explainable usefulness ranking** (§7.2: goal-relevance + urgency + interest-match + timing-fit +
  novelty − fatigue) against the user model → top‑K (cap ~3/window) → cards in the Phase-3 feed; every
  card answers **"why am I seeing this?"**.
- **5c — Feedback + scheduler:** `Outcome` (acted/dismissed/ignored/more|less) deterministically updates
  the user model + ranker weights (§7.5) and **measurably shifts** future ranking; **explore/exploit**
  (§7.3, ε decays as confidence rises); suggestions frequency-capped + tunable + off-switch; the
  **scheduler** runs reflection on its threshold and the candidate→rank pass on schedule/events and
  pushes to the feed; the **daily briefing finally fires automatically** (deferred from Phase 2). **A
  test proves the objective is usefulness, not engagement.**

## Decisions / open questions (Core §11 — resolved via the review; one needs the user)

1. **Reflection trigger fuel** — accumulate deterministic per-kind **trigger fuel** over signals since
   the last **seq** baseline; threshold + fuel weights in config; attention kinds denylisted to 0.0.
   (Faithful to §7.4, adapted to Phase-2 explicit-only memory; fuel ≠ feedback reward.)
2. **What reflection learns from where** — **rhythms/cadence/modality from the signal log; interests/
   preferences from the explicit memory corpus + goals** (the signal log has no topics). Confidence is
   the pinned `confidence_after` function. User model = materialized row + live goals.
3. **THE one to confirm (Ask First — trust boundary):** to derive interest-from-behavior in 5b, do we
   add a **bounded capability-domain enum tag** (`finance|calendar|knowledge|goals`, derived from the
   capability, never from query text) to signal payloads? **Default = NO** (5a stays honest: interests
   come from memories+goals). Adding it later is a conscious metadata-boundary decision, not assumed.
4. **`SPEC.md` is the Phase 5 (5a-active) spec**; a copy at `docs/specs/phase-5.md`. 5b/5c get their own
   spec on ship of 5a.

## Build-time verifications (source-driven, at the start of the relevant slice)

- **5a:** re-confirm the installed Ollama JSON-schema-constrained generation path (the Phase-1 router
  pattern) for the reflection synthesis output, and the existing `MemoryStore.retrieve` / signal-log
  query shapes the context builder depends on.
- **5b/5c:** verify any scheduler primitive before wiring the always-on pass (Core §9 Heartbeat role).

## Build Order (for /plan — 5a active; carve 5b/5c when 5a ships)

**5a (this build):**
1. **Reflection trigger** — §7.4 deterministic accumulation + per-kind signal importance; reflection state.
2. **Reflection context + synthesis** — deterministic aggregation + memory retrieval → grounded LLM
   synthesis → typed, validated, source-linked `reflection` memories.
3. **User model** — materialized, inspectable `UserModel`; deterministic merge with confidence rise/decay;
   `:reflect` / `:profile`.

**5b (next spec→ship):** 4. Candidate generation (deterministic triggers). 5. Usefulness ranking (§7.2,
explainable) → top-K to the feed.

**5c (next spec→ship):** 6. Feedback loop + explore/exploit (§7.5/§7.3). 7. Scheduler + auto-briefing.

Then `/test` → the **heavier multi-lens adversarial review** (including a dedicated "could this objective
drift toward engagement / become manipulative?" lens) → `/code-simplify` → `/ship`, recording learnings
to `docs/DECISIONS.md`.
