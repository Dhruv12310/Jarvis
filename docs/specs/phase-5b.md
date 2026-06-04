# Spec: Jarvis — Phase 5b (Proactivity Engine: candidate generation + usefulness ranking)

> Focused spec for the **active** sub-phase. Phase 5 runs as **5a → 5b → 5c**, each its own
> `/spec → /ship` cycle. **5a (Reflection + User Model) is shipped** (`docs/specs/phase-5.md`,
> commits through `d08b03b`). **THIS is 5b.** 5c (feedback loop + explore/exploit + scheduler +
> auto-briefing) remains the binding north star (last section), specified on 5b's ship.
>
> Design source-of-truth: `CLAUDE.md` (invariants) + `docs/Jarvis_Core_Spec.md` — 5b implements
> **Core Stage 6** (the two-stage recommender): §5.5 (`Suggestion`/`Outcome`), §6 Stage 6, §7.2
> (ranking — "the soul of the system"), and **§8 (the objective constraint — the heart)**. 5a
> learnings: `docs/DECISIONS.md` (Phase 5a + D23). The `UserModel` 5a materialized is what 5b ranks
> against; the Phase-3 `Feed.post_card` surface is where 5b's cards land.

## Objective

Turn knowing-the-user (5a) into **useful, surfaced suggestions**. 5b builds the **two-stage
recommender** (Covington et al., RecSys 2016) as deterministic code: **candidate generation** (wide,
cheap, high-recall) → **usefulness ranking** (§7.2, explainable, high-precision) → an **abstention +
frequency gate** → the **top-K (0..3) cards** pushed to the Phase-3 desktop feed, each answering
**"why am I seeing this?"**. The local LLM **phrases** the card; it **never ranks or selects**.

5b does NOT learn from outcomes yet (that is 5c). It produces and surfaces; it persists each
`Suggestion` so 5c can attach `Outcome`s and tune. **Run on demand** in 5b (`:suggest`, a feed
refresh); the always-on scheduler + two-channel digest are 5c.

## THE ethical constraint (non-negotiable — Core §8, the heart of this phase)

**The ranker optimizes for USEFULNESS — did this save me time, advance a declared goal, or prevent a
miss — NEVER engagement, attention, time-on-app, dwell, click-through-as-an-end, or notification
volume.** *Instagram's mechanism (two-stage recommender), not its objective (capturing attention).*
The research that grounded this spec (Horvitz attention-cost / net-value-of-alerting; Stray & Thorburn
on value-vs-engagement; Goodhart-in-RL; Chow's reject rule) converges on one truth: **no proxy is
unhackable, so the guards must be structural, not a clever reward.** Made code in 5b, each with a test:

1. **No attention feature, ever.** A ranking feature may NEVER derive from `dwell`, `shown`, opens,
   session length, return frequency, CTR-as-an-end, or notification volume. Features come only from
   goals, deadlines, timing/rhythms, the user model's **goal-linked** interest weights, and
   counterfactual novelty. A boundary test pins the feature set to the fixed §7.2 list.
2. **A compulsion cannot climb the ranker.** `interest_match` reads only `Interest.weight`, which 5a
   pins to **0.0 for pure-frequency (non-goal-linked) interests**. So a high-frequency non-goal topic
   contributes **0** interest score. (Structural continuation of the 5a §8 guard; re-tested here.)
3. **Abstention is the DEFAULT, not an edge case.** Surface only candidates clearing an **absolute**
   `usefulness_threshold` set HIGH (precision ≫ recall — a bad *push* costs trust, asymmetrically:
   Horvitz net-value, Chow reject). **Show-nothing (0 cards) is a frequent, correct output.** A test
   asserts an empty/weak pool yields zero cards.
4. **The frequency cap is STRUCTURAL** — a config constant outside the scorer, so **no score, weight,
   or feedback can ever raise volume.** Cap ~3 per window + per-category cap + per-entity cooldown. A
   test asserts the cap holds even when many candidates clear the threshold.
5. **"Why am I seeing this?" is deterministic code, not an LLM verdict.** Each card's explanation is
   the generator's provenance + the per-feature score contributions (the linear, monotone ranker makes
   these printable). The LLM only phrases the human body. A test asserts the "why" resolves to real
   source records, and a boundary test asserts the ranking modules import no LLM.
6. **Counterfactual / incremental value.** Serendipity = unexpectedness × utility: **zero credit for
   what the user already knew or has already been shown.** Novelty + cooldown enforce it.
7. **The β weights are documented + inspectable** (a "reward report"): `:why` / a weights dump shows
   every weight and each card's contribution breakdown. The objective is auditable by the user.
8. **Autonomy:** suggestions are dismissable, the watchlist is the user's, DND/quiet-hours **suppress
   all**, and proactivity can be turned down/off. The system serves me, not the reverse.

## What 5b adds beyond the original north star (folded in from the research — BINDING)

- **Abstain-by-default with an absolute (not min-max) threshold.** The §7.1 retrieval formula min-max
  normalizes terms over the candidate set; the **ranker must NOT** — min-max over a tiny/empty pool
  makes one candidate normalize to 1.0 and destroys abstention. 5b uses **calibrated absolute [0,1]
  features** so the threshold means "useful enough to interrupt," and 0 cards is reachable.
- **Asymmetric-cost posture:** bias toward silence. Rank hard, show little, often show nothing.
- **DND/quiet-hours is a hard gate**, not just a soft `timing_fit` term.
- **Trust-boundary tightening for collector candidates:** collector queries use only an **explicit,
  public watchlist** (symbols/topics the user sets). Private goal text / memory content / amounts are
  **never** sent to a public collector API. Auto-deriving collector queries from private data is
  **Ask First** (deferred to a conscious decision).

## Trust boundary

- **Candidate generation, ranking, selection, and persistence run LOCALLY.** The user model, goals,
  finance, memories, and `Suggestion`s never leave the machine.
- **The only outbound path is the existing Collectors** (Phase 1, public APIs), queried **only with
  public watchlist terms**. No private data crosses out to fetch candidates.
- **The only model call in 5b is local Ollama** — **phrasing the card body only** (Tier 1, on the
  Brain; the deterministic engine runs on the always-on Heartbeat). The LLM never scores or selects.
- **Signal log stays metadata-only:** the `suggest` run signal and the `suggestion_shown` marker carry
  counts/types/ids only — never card text, amounts, or topics. `suggestion_shown` is attention →
  **0.0 trigger fuel** (5a denylist) and is **never** a positive reward (that is 5c's law).

## Tech Stack

| Concern | Choice | Why |
|---|---|---|
| Candidate generators, features, ranker, gate | pure Python (deterministic) | §7.2 is explainable code; testable; free; no attention inputs |
| Card phrasing | local Ollama `LLMClient` (existing) | Tier-1 phrasing only; ranking/selection/"why" stay code |
| Collector candidate data | existing Phase-1 `Connector.fetch` | The one outbound seam; public watchlist terms only |
| Candidate sources (owned) | `JarvisService` facade (goals/budget/calendar/recurring) | Deterministic over data Jarvis already owns |
| Watchlist + `Suggestion` persistence | `StructuredStore` (SQLite) | User-owned watch terms + surfaced-suggestion log for 5c; raw SQL only in sqlite module |
| Delivery | Phase-3 `Feed.post_card` + `AppController` | The receive surface already built for exactly this |

**No new runtime deps** (ranker stays hand-weighted/linear per §7.2 / §11; an ML lib is a 5c+ decision
once a labeled `Outcome` set exists).

## Project Structure (5b)

```
jarvis/proactivity/
  candidate.py     # Candidate + Provenance value objects; CandidateGenerator Protocol + registry
  generators.py    # deterministic triggers: owned (goal_deadline, stale_goal, budget_threshold,
                   #   recurring_bill_due, event_prep, free_hour) + collector (market_move,
                   #   watched_news, yc_launch) reading connectors with PUBLIC watchlist terms
  features.py      # calibrated [0,1] monotone feature fns (PURE: no LLM, no HTTP, no attention data)
  rank.py          # usefulness(c, ctx, user)=Σβ·f (§7.2); abstain @ absolute threshold; freq cap +
                   #   per-category cap + cooldown + DND gate; select top-K (PURE)
  phrase.py        # the ONLY 5b LLM: phrase a selected candidate -> card body (phrasing only)
  suggest.py       # engine: generate -> rank -> gate -> phrase -> persist Suggestion -> [Card]
stores/
  structured.py    # += Watchlist CRUD; Suggestion save + recent-surfaced query (for cooldown/fatigue)
  sqlite_store.py  # += watchlist + suggestions tables (raw SQL stays here)
jarvis/config.py   # += β weights (β_goal/urgency/interest/timing/novelty/fatigue), usefulness_threshold,
                   #   suggestions_per_window + window, per_category_cap, entity_cooldown, urgency_horizon,
                   #   market_move_pct, recency λ for novelty
service.py         # += suggestions() (run engine -> cards) ; watchlist add/list/remove
ui/controller.py   # += show_suggestions() (post Suggestion cards w/ deterministic "why")
cli.py/__main__.py # += :suggest, :watch (add|list|rm) ; `suggest` subcommand
tests/
  test_candidate_generators.py  # each generator fires on the right state, abstains otherwise (fakes)
  test_proactivity_features.py  # each feature exact [0,1], monotone; interest_match=0 for pure-freq
  test_rank.py                  # §7.2 sum; absolute threshold abstains; cap/cooldown/DND; top-K order
  test_suggest_engine.py        # generate->rank->gate->phrase (fake LLM); persists Suggestion; "why" code
  test_watchlist_store.py       # watchlist + suggestions round-trip (temp SQLite)
  test_boundaries.py            # += features/rank/candidate import no LLM, no httpx; collector terms public
  + facade/controller tests in test_service.py / test_controller.py
```

## Data model (Core §5.5)

```python
@dataclass(frozen=True)
class Provenance:
    generator: str            # which trigger fired ("goal_deadline", "market_move", ...)
    reason: str               # deterministic human "why" ("goal #7 'ship 5b' due in 2 days")
    source_ids: list[str]     # ids that must resolve to real records ("goal:7", "budget:dining", "markets:NVDA")

@dataclass(frozen=True)
class Candidate:
    type: str                 # candidate_type enum (§5.5): market_move|free_time|followup_due|goal_nudge|budget_alert|...
    entity_key: str           # dedup + cooldown key ("goal:7", "symbol:NVDA", "budget:dining")
    features: dict[str, float] # raw deterministic inputs (deadline_hours, change_pct, over_by, ...)
    provenance: Provenance
    payload: dict             # LOCAL data the phraser needs (goal desc, pct, amount) - never logged/sent out

@dataclass(frozen=True)
class ScoredCandidate:
    candidate: Candidate
    score: float
    contributions: dict[str, float]   # per-feature β·f -> the explainable "why" (the reward report)

# Suggestion (persisted, §5.5): id, created_at, candidate_type, content (LLM body),
#   features (json = contributions), score, surfaced (bool), channel ("feed")
```

## Core formula (Core §7.2 — implemented exactly, absolute features)

```
usefulness(c, ctx, user) =
      β_goal     · goal_relevance(c, user.goals)        # serves a declared goal? (graded by priority)
    + β_urgency  · urgency(c)                           # monotone-decreasing in time-to-deadline/event
    + β_interest · interest_match(c, user.interests)    # max goal-linked Interest.weight (0 for pure-freq)
    + β_timing   · timing_fit(ctx.now, user.rhythms, user.dnd)   # opportune-moment fit
    + β_novelty  · novelty(c, recent_suggestions)       # incremental value: NOT already-shown/known
    - β_fatigue  · recent_interruption_penalty(ctx)     # suppress spam

# each f ∈ [0,1], CALIBRATED + monotone (NOT min-max normalized — that would break abstention).
# surface candidates where usefulness >= usefulness_threshold (absolute, HIGH); else nothing.
# then: DND gate (suppress all) -> per-entity cooldown -> per-category cap -> global cap (~3/window).
# β weights hand-set in config (documented); LEARNED from Outcomes in 5c (§7.5). 5b: β_novelty's
# explore term is the deterministic incremental-value sense; ε-exploration (§7.3) is 5c.
```

## Candidate generators (registry of pure triggers; each `(state, now) -> [Candidate]`)

**Owned-data (fully deterministic, no egress):**
- `goal_deadline` — active goal with `deadline` within `urgency_horizon` → `goal_nudge`.
- `stale_goal` — active goal untouched > N days (no recent progress) → `goal_nudge`.
- `budget_threshold` — `budget_status` over (or near) limit this month → `budget_alert`.
- `recurring_bill_due` — `recurring_charges` with next occurrence soon → `followup_due`.
- `event_prep` / `free_hour` — calendar event approaching with no linked prep / a free hour before a
  meeting → `free_time`.

**Collector-driven (egress via existing connectors, PUBLIC watchlist terms only):**
- `market_move` — markets connector over watchlist **symbols**; `|Item.extra.change_pct|` ≥
  `market_move_pct` → `market_move`.
- `watched_news` / `yc_launch` — news / HN connector over watchlist **topics**; matching items →
  `yc_launch` / project-relevant card.

Generators run independently, **union**, dedup by `entity_key`. Each tags `Provenance` (free "why").
The watchlist is **explicit + user-owned** (`:watch add NVDA`, `:watch add topic "local LLMs"`);
auto-deriving terms from private goals/memories is **Ask First** (deferred).

## Commands (5b)

```bash
python -m jarvis                 # CLI: + :suggest (run engine, print ranked cards + why), :watch
python -m jarvis suggest         # run the engine once (Heartbeat job), surface to the feed, exit
pytest -q                        # offline: generators/features/ranker/engine with the LLM + connectors faked
pytest -q -m integration         # live: phrasing against real Ollama; collector candidates against live APIs
ruff check . ; ruff format --check .
```

## Testing Strategy (5b)

- **Generators (unit):** each fires on the right fixture state and **abstains otherwise**; collector
  generators query with **public watchlist terms only** (assert no private text in the query); dedup by
  entity_key. Connectors + facade faked.
- **Features (unit):** each feature is exact, in [0,1], and **monotone** (urgency rises as deadline
  nears; novelty falls for already-shown). **§8 guard: `interest_match` returns 0 for a high-frequency
  non-goal interest, > 0 only for a goal-linked one.**
- **Ranker (unit):** `usefulness` equals the weighted sum to exact values; **absolute threshold makes
  a weak pool yield nothing**; the **global cap holds when many candidates clear threshold**;
  per-category cap, per-entity cooldown, and the **DND gate suppress correctly**; top-K ordering.
- **Engine (unit):** generate→rank→gate with a **fake LLM** phraser writes cards whose **"why" is
  deterministic** (resolves to real source ids) and persists a `Suggestion` per surfaced card; the
  `suggest` signal is **metadata-only**.
- **Boundary:** `features.py`/`rank.py`/`candidate.py` import **no LLM and no httpx**; only `phrase.py`
  imports the model; collector generators reach HTTP only via connectors.
- **Store (unit):** watchlist + `Suggestion` round-trip (temp SQLite); recent-surfaced query.
- **Integration (`-m integration`):** real Ollama phrasing + live collector candidates, gated like
  prior phases.

## Boundaries

- **Always:** ranking/selection/"why" are deterministic explainable code; the LLM only phrases;
  everything runs locally; collector queries use public watchlist terms only; the signal log stays
  metadata-only; abstention + the structural frequency cap are the default posture; `pytest` + `ruff`
  before each commit; commit per slice; conventional commits (no em-dashes, no attribution).
- **Ask First:** any new dependency (5b needs none); changing `MemoryRecord`/`SignalEvent`/
  `StructuredStore`/`Connector` interfaces; **deriving collector queries from private goals/memories**;
  any new outbound destination.
- **Never:** optimize for engagement/attention/dwell/time-on-app/notification volume; let an attention
  signal raise a score or the frequency; let the LLM score, select, or invent the "why"; min-max the
  ranker features (breaks abstention); send private data to a collector; build the mobile surface, the
  scheduler/auto-briefing, the feedback-learning loop, or explore/exploit (those are 5c / Phase 6);
  give financial advice (finance cards surface opted-in facts only).

## Success Criteria — 5b Definition of Done (testable)

1. **Two-stage engine runs** on demand: deterministic generators produce a candidate pool; the §7.2
   ranker scores each; the gate selects **top-K (0..3) or nothing**; survivors become **cards in the
   Phase-3 feed**, each with a deterministic **"why am I seeing this?"**.
2. **Candidate generators** cover owned data (goal deadline/stale, budget threshold, recurring bill,
   event prep/free hour) **and** collector-driven (market move, watched news/YC) over a **user-owned
   public watchlist** — each unit-tested to fire and to abstain.
3. **The ranker is explainable code** (§7.2): the score is the weighted sum of calibrated [0,1]
   features; per-feature contributions are inspectable; β weights live documented in config.
4. **The usefulness law is enforced in code, not prose** (tests): no feature derives from attention;
   `interest_match` is 0 for pure-frequency interest; a weak/empty pool surfaces **nothing**; the
   **structural cap** bounds volume regardless of scores; the ranking modules import no LLM; the "why"
   resolves to real records.
5. **Abstention + asymmetric cost are real:** show-nothing is a normal output; DND suppresses all;
   per-entity cooldown prevents re-surfacing what was already shown (counterfactual novelty).
6. **Each surfaced `Suggestion` is persisted** (§5.5) so 5c can attach `Outcome`s; the `suggest` run
   and `suggestion_shown` are metadata-only and carry 0 trigger fuel.
7. **The user controls it:** `:suggest` to run, `:watch` to manage sources, `:why` shows each card's
   provenance + contribution breakdown, dismissable, DND/off honored. Everything local; `pytest -q`
   passes fully offline; phrasing + live collectors are integration-gated; `ruff` clean.

## Build-time verification (source-driven, at the relevant slice)

- Before the collector-generator slice: re-confirm each connector's `Item.extra` fields (markets
  `change_pct`, HN/news shapes) and the `fetch(query)` contract the generators depend on.
- Re-confirm the 5a `UserModel` shape the ranker reads (`Interest.weight` goal-linked semantics,
  `rhythms`, `dnd`/preferences) and the facade methods the generators read.

## Build Order (for /plan)

1. **Candidate model + registry + owned-data generators** (goal/budget/calendar/recurring) — pure,
   faked facade. *Prove generation + provenance + dedup.*
2. **Watchlist (store CRUD + `:watch`) + collector generators** (market_move/watched_news/yc_launch)
   over public terms — connectors faked; trust-boundary test (no private text in queries).
3. **Features + ranker + gate** (§7.2 sum; absolute-threshold abstention; cap/cooldown/DND; top-K) —
   pure, exact-value tests including the §8 guards.
4. **Engine orchestration + `Suggestion` persistence + LLM phrasing + facade/controller/CLI wiring** —
   generate→rank→gate→phrase→post; metadata-only signal; integration-gated live path.

Then `/test` → the **heavier multi-lens adversarial review** (with the dedicated "could this objective
drift toward engagement / become manipulative?" lens, now against a real ranker) → `/code-simplify` →
`/ship`, recording learnings to `docs/DECISIONS.md`.

## North star — Phase 5 Definition of Done (5c, specified, built next)

- **5c — Feedback + scheduler:** `Outcome` (acted/dismissed/ignored/more|less) deterministically
  updates memory importance (Stage 2), the user model (Stage 5), and the ranker β weights (§7.5) and
  **measurably shifts** future ranking; **value-corroborated reward only** (acted-AND-good-outcome /
  explicit helpful — `acted` alone is non-positive; `shown`/`dwell` never positive; reward weighted by
  value **magnitude**, not event count); **explore/exploit** (§7.3 — per-category Thompson/ε-greedy
  with a pessimistic cold-start prior, exploration changes *which* slot fills, never whether/volume,
  ε decays as confidence rises); **a holdout explicit-value metric the optimizer never trains on**
  (drift alarm if proxy ↑ while holdout ↓); dismissal tightens a per-category **exponential-backoff
  cooldown**; the **scheduler** (always-on Heartbeat) runs reflection on its threshold and the
  candidate→rank pass on schedule/events, delivering a **once-daily digest** (default sink) + event-
  triggered real-time only for time-critical, high-confidence items; the **daily briefing fires
  automatically** (deferred from Phase 2). **A test proves the objective is usefulness, not
  engagement.**
```
