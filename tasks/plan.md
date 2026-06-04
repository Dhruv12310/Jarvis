# Phase 5b — Plan (Proactivity Engine: candidate generation + usefulness ranking)

> Spec: `SPEC.md` / `docs/specs/phase-5b.md`. Implements Core **Stage 6** (two-stage recommender):
> §5.5 (`Suggestion`), §7.2 (ranking), **§8 (usefulness, never engagement)**. 5a (Reflection + User
> Model) is shipped; 5b ranks against the `UserModel` it built and pushes cards to the Phase-3
> `Feed.post_card`. **5c (feedback / explore-exploit / scheduler / auto-briefing) is NOT in scope.**

## Design spine (the one architectural decision everything hangs on)

**Generators and the ranker are PURE functions of an injected `EngineState` snapshot; only the engine
(`suggest.py`) does I/O.** The engine gathers goals / budget / transactions / calendar / user model /
watchlist / recent suggestions / connector items **once**, hands a frozen snapshot to the pure
pipeline, then phrases + persists + posts. This makes every generator, feature, and the ranker
unit-testable with plain fixtures (no facade, no Ollama, no HTTP, no clock) and keeps the trust
boundary in one auditable place.

```
suggest.py (ENGINE, the only I/O)
   gather EngineState ──► generate (registry of pure generators) ──► union + dedup by entity_key
        │                                                                      │
        │                                              rank.py (PURE): usefulness=Σβ·f (§7.2)
        │                                                 ─► abstain @ absolute threshold
        │                                                 ─► DND gate ─► cooldown ─► per-cat cap ─► global cap
        │                                                                      │  top-K (0..3) ScoredCandidate
        ▼                                                                      ▼
   phrase.py (LLM: body only) ──► persist Suggestion (§5.5) ──► Card{body, why(code)} ──► Feed
```

`EngineState` (frozen; grows across slices):
```
now; goals[active]; budget_status[]; transactions[]; events[];          # S1 owned inputs
user_model; recent_suggestions[];                                       # S3/S4 ranker + novelty inputs
watch_symbols[]; watch_topics[]; connector_items{markets|news|hn: [Item]}  # S2 collector inputs
```

## Source-driven findings (verified in code — bind the design)

- **`config.market_watchlist` already exists** (env, default `AAPL,MSFT,…`). The new watchlist store
  adds **runtime-editable topics** (news/HN) + optional extra symbols; the market generator uses
  store symbols **∪ `config.market_watchlist`** as fallback. Don't duplicate the symbol list.
- **`Recurring(merchant, amount, count, cadence)` has NO next-due date.** `recurring_bill_due` computes
  `next = last_txn.date + cadence_days` from the transactions and checks the horizon.
- **`Goal` has NO `updated_at`** (id, description, status, progress, priority, deadline, created_at).
  `stale_goal` uses `created_at` age + `progress < 1.0` as the staleness proxy; a precise "last
  touched" is an **Ask-First** Goal-schema change (not in 5b).
- **`UserModel` has NO `dnd`** (interests, rhythms, preferences, goals, updated_at). DND + the hard
  quiet-hours gate come from **config** (`quiet_hours_start/end`, `proactivity_enabled`); `timing_fit`
  reads `rhythms` + those config hours.
- **Markets `Item.extra = {change_pct, price, prev_close}`** (confirmed) → `market_move` thresholds on
  `abs(change_pct) >= market_move_pct`. **`CalendarEvent(summary, start, end, location, all_day)`** →
  `event_prep` fires for the next **timed** event with `start` within `urgency_horizon`.
- **`BudgetStatus(category, limit, actual, remaining, over)`** → `budget_threshold` fires on `over` or
  `remaining < near_fraction * limit`.

## Dependency graph

```
S1 candidate.py (Candidate/Provenance/Protocol/registry) ─┬─► S1 owned generators ─┐
                                                          │                        │
S2 watchlist store + :watch ──► S2 collector generators ──┘                        ├─► S4 suggest.py engine
S3 features.py (pure) ──► S3 rank.py (pure: §7.2 + gate) ───────────────────────────┤   + phrase.py (LLM)
config.py additions (land in the slice that first needs them)                       │   + Suggestion persist
S4 Suggestion persistence + service.suggestions() + controller + CLI ◄──────────────┘   + facade/UI/CLI wiring
```
No cycles: `rank.py` takes `recent_suggestions` as injected data (fixtures in S3); the engine supplies
the persisted list in S4.

---

## Slice 1 — Candidate model + registry + owned-data generators
`feat(proactivity): candidate generation over owned data (goals, budget, recurring, calendar)`

**Source-verify first:** `Goal` / `BudgetStatus` / `Recurring` / `CalendarEvent` shapes (done above);
confirm `engine.recurring_charges(transactions)` + `engine.budget_vs_actual` outputs.

**Build:**
- `proactivity/candidate.py` — `@dataclass(frozen=True) Provenance(generator, reason, source_ids)`;
  `Candidate(type, entity_key, features: dict[str,float], provenance, payload: dict)`;
  `CandidateGenerator` Protocol (`__call__(state) -> list[Candidate]`); `GENERATORS` registry list +
  `generate_all(state)` that unions every generator and **dedups by `entity_key`** (first wins).
- `proactivity/generators.py` — owned generators, each pure `(state) -> [Candidate]`:
  - `goal_deadline` — active goal, `deadline` within `urgency_horizon` → `goal_nudge`,
    `entity_key="goal:{id}"`, provenance reason from deadline, `source_ids=["goal:{id}"]`.
  - `stale_goal` — active, `progress < 1.0`, `created_at` older than `stale_goal_days`, no near
    deadline → `goal_nudge` (same entity_key; dedup with goal_deadline → deadline wins).
  - `budget_threshold` — `BudgetStatus.over` or `remaining < near_fraction*limit` → `budget_alert`,
    `entity_key="budget:{category}"`.
  - `recurring_bill_due` — `recurring_charges`; `next = last_txn.date + cadence`; within horizon →
    `followup_due`, `entity_key="recurring:{merchant}"`.
  - `event_prep` — next **timed** event (`not all_day`) starting within `urgency_horizon` →
    `free_time`, `entity_key="event:{start_iso}:{summary}"`.

**Acceptance:** each generator fires on a fixture state and **abstains** on empty/irrelevant state;
every candidate carries a non-empty `provenance.reason` + `source_ids`; `generate_all` unions and
**dedups by entity_key**; payload holds only local data (no signal/attention fields). Generators make
**no facade/HTTP/LLM calls** (state injected).
**Verify:** `pytest -q tests/test_candidate_generators.py` ; `ruff check .`
**Files:** `proactivity/candidate.py`, `proactivity/generators.py`, `tests/test_candidate_generators.py`.

---

## Slice 2 — Watchlist (store + `:watch`) + collector generators
`feat(proactivity): user-owned public watchlist and collector candidate generators (market/news/yc)`

**Source-verify first:** markets `Item.extra.change_pct` (confirmed); HN/news `Item` shapes; the
`Connector.fetch(query)` contract; `config.market_watchlist`.

**Build:**
- `stores/structured.py` + `sqlite_store.py` — `Watchlist` CRUD: `add_watch(kind, value)` /
  `get_watchlist()` / `remove_watch(kind, value)`; `watchlist(kind TEXT, value TEXT, UNIQUE)` table
  (`kind ∈ {symbol, topic}`; raw SQL only in sqlite module).
- `cli.py` — `:watch add <symbol|topic> <value>` / `:watch list` / `:watch rm …`.
- `proactivity/generators.py` — collector generators, pure over `state.connector_items`:
  - `market_move` — items where `abs(extra.change_pct) >= market_move_pct` → `market_move`,
    `entity_key="symbol:{title}"`.
  - `watched_news` / `yc_launch` — news / HN items for watch topics → `yc_launch` /
    project-relevant card, `entity_key="news:{url|title}"`.
- The **engine** (S4) fetches items using **only watchlist terms** (symbols ∪ config fallback;
  topics); generators never see private text.

**Acceptance:** watchlist round-trips (temp SQLite); `:watch` add/list/rm work; collector generators
fire on matching `Item`s and abstain otherwise; **trust-boundary test: the query terms passed to any
connector come only from the watchlist (public) — a test asserts no goal/memory/payload text can enter
a collector query.**
**Verify:** `pytest -q tests/test_watchlist_store.py tests/test_candidate_generators.py` ; `ruff check .`
**Files:** `stores/structured.py`, `stores/sqlite_store.py`, `cli.py`, `proactivity/generators.py`,
`config.py` (+`market_move_pct`), `tests/test_watchlist_store.py`, `tests/test_candidate_generators.py`,
`tests/test_boundaries.py` (collector-terms-are-public guard).

---

## Slice 3 — Features + ranker + gate (§7.2, the soul) — PURE
`feat(proactivity): explainable usefulness ranking with abstention and a structural frequency cap`

**Source-verify first:** the 5a `UserModel` shape the ranker reads — `Interest(topic, weight,
confidence, …)` with **`weight == 0.0` for pure-frequency (non-goal-linked)** interests, `rhythms`,
`preferences`; confirm there is **no `dnd`** (→ config quiet-hours).

**Build (no LLM, no httpx, no attention data anywhere in these modules):**
- `proactivity/features.py` — calibrated `[0,1]` **monotone** feature fns:
  - `goal_relevance(c, goals)` — serves an active goal? graded by `priority`; else 0.
  - `urgency(c)` — monotone-decreasing in `features["deadline_hours"]` / event horizon; 0 beyond.
  - `interest_match(c, interests)` — **max goal-linked `Interest.weight`** over topic matches (0 for
    pure-frequency → the §8 guard); else 0.
  - `timing_fit(now, rhythms, *, quiet_hours)` — opportune-moment fit; 0 inside quiet hours.
  - `novelty(c, recent_suggestions, *, lam)` — incremental value: decays toward 0 for an
    entity already surfaced recently (recency `lam`); ~1 for unseen.
  - `recent_interruption_penalty(recent_suggestions, *, now, window)` — the `−β_fatigue` term.
- `proactivity/rank.py` —
  - `usefulness(c, state) -> (score, contributions)` = `β_goal·goal_relevance + β_urgency·urgency +
    β_interest·interest_match + β_timing·timing_fit + β_novelty·novelty − β_fatigue·penalty`
    (**absolute features; NO min-max normalization**). `contributions` = per-term `β·f` (the "why").
  - `select(candidates, state) -> list[ScoredCandidate]` — score all → **abstain**: drop
    `score < usefulness_threshold` → **DND gate**: if `not proactivity_enabled` or `now` in quiet
    hours → return `[]` → **per-entity cooldown**: skip `entity_key` surfaced within `entity_cooldown`
    → **per-category cap** (`≤ per_category_cap` per `type`) → **global cap**
    (`suggestions_per_window` minus already-surfaced-in-window) → top-K sorted by score.
- `config.py` — `β_goal, β_urgency, β_interest, β_timing, β_novelty, β_fatigue`,
  `usefulness_threshold` (HIGH), `suggestions_per_window` (3), `suggestion_window_hours`,
  `per_category_cap` (1), `entity_cooldown_hours`, `urgency_horizon_hours`, `stale_goal_days`,
  `novelty_lambda`, `quiet_hours_start`, `quiet_hours_end`, `proactivity_enabled`.

**Acceptance (exact-value tests) + the §8 guards, each its own test:**
- `usefulness` equals the weighted sum to exact values; `contributions` sums to `score`.
- **No attention feature exists** — a test pins the feature set to the §7.2 list (no dwell/shown/opens).
- **`interest_match == 0` for a high-frequency non-goal interest**, `> 0` only goal-linked.
- **Weak/empty pool → `select` returns `[]`** (abstention default).
- **Structural cap bounds volume** — feed 10 candidates all above threshold → `len ≤ suggestions_per_window`.
- per-category cap, per-entity cooldown, and **DND gate suppress** correctly; top-K ordering by score.
- **Boundary:** `features.py` / `rank.py` / `candidate.py` import **no LLM and no httpx**.
**Verify:** `pytest -q tests/test_proactivity_features.py tests/test_rank.py tests/test_boundaries.py` ; `ruff check .`
**Files:** `proactivity/features.py`, `proactivity/rank.py`, `config.py`,
`tests/test_proactivity_features.py`, `tests/test_rank.py`, `tests/test_boundaries.py`.

---

## Slice 4 — Engine + Suggestion persistence + LLM phrasing + wiring
`feat(proactivity): suggestion engine - generate, rank, phrase, persist, post to the feed`

**Source-verify first:** the facade read methods (`get_goals(status=active)`, `budget_status`,
`get_transactions`, `_calendar_events`), the `Connector` handles available to the service, and the
`Feed.Card` shape (extend with an optional `why`).

**Build:**
- `proactivity/phrase.py` — the **only** 5b LLM: `phrase(scored, llm) -> str` writes a short card body
  from `payload` + `provenance.reason`. **Phrasing only**; never scores/selects/invents the "why".
- `proactivity/suggest.py` — `run(*, facade-handles, connectors, llm, now) -> list[Card]`: gather
  `EngineState` (fetch connector items using **watchlist terms only**), `generate_all` → `select` →
  `phrase` survivors → persist each as `Suggestion(surfaced=True, channel="feed",
  features=contributions, score)` → build `Card(body=LLM, why=provenance.reason + top contributions,
  kind="suggestion")`. Abstention → `[]`.
- `stores/structured.py` + `sqlite_store.py` — `save_suggestion(s)` + `get_recent_suggestions(since)`;
  `suggestions` table (§5.5: id, created_at, candidate_type, content, features json, score, surfaced,
  channel).
- `service.py` — `suggestions() -> list[Card]` (runs the engine via the facade's existing handles);
  `add_watch/list_watch/remove_watch`; emit a **metadata-only** `suggest` signal (counts: generated /
  surfaced) and a **metadata-only** `suggestion_shown` per surfaced card (0 trigger fuel — already
  denylisted in 5a; re-assert here).
- `ui/feed.py` — `Card` gets optional `why: str | None = None`; `ui/controller.py` —
  `show_suggestions()` posts the cards (body + why).
- `cli.py` / `__main__.py` — `:suggest` (run engine, print each card + "why am I seeing this");
  `suggest` subcommand (`python -m jarvis suggest`).

**Acceptance:** engine end-to-end with a **fake LLM** + faked facade/connectors → `Card`s whose **why
is deterministic and resolves to real source ids**; a `Suggestion` row persists per surfaced card;
abstention prints "(nothing worth surfacing right now)"; the `suggest` + `suggestion_shown` signals are
**metadata-only** (a test asserts no card text/topic/amount in the payload); `:suggest` and the
subcommand work offline. Live Ollama phrasing + live collectors are **integration-gated** (`-m integration`).
**Verify:** `pytest -q` (full, offline) ; `pytest -q -m integration` (live) ; `ruff check . ; ruff format --check .`
**Files:** `proactivity/suggest.py`, `proactivity/phrase.py`, `stores/structured.py`,
`stores/sqlite_store.py`, `service.py`, `ui/feed.py`, `ui/controller.py`, `cli.py`, `__main__.py`,
`tests/test_suggest_engine.py`, `tests/test_service.py`, `tests/test_controller.py`.

---

### ▸ Checkpoint: 5b feature-complete (all 4 slices, pytest + ruff green) →
`/test` → **heavier multi-lens adversarial review** (code-reviewer + security/privacy + the dedicated
"could this objective drift toward engagement / become manipulative?" lens, now against a real ranker)
→ fix findings → `/code-simplify` → `/ship` (3-persona fan-out, push) → record learnings in
`docs/DECISIONS.md`. **THEN spec 5c.**

## Guardrails held throughout
- Deterministic-first: generation, features, ranking, selection, the "why" are **code**; the LLM only
  phrases. Boundary tests enforce it.
- Trust boundary: collector queries use **public watchlist terms only**; no private data leaves; the
  signal log stays metadata-only.
- **Usefulness, never engagement:** no attention feature; a compulsion can't climb (`interest_match=0`
  for pure-frequency); abstention is the default; the frequency cap is structural.
- Minimalism: no ML library, no scheduler, no feedback loop, no explore/exploit (all 5c). Commit per
  slice; conventional commits (no em-dashes, no attribution); `pytest` + `ruff` before each commit.

## North star (5c, next cycle) — for context, NOT this build
`Outcome` (acted/dismissed/…) → value-corroborated reward (acted-AND-good-outcome / explicit helpful;
`acted` alone non-positive; reward by **magnitude**, not count) updates user model + β weights (§7.5);
**holdout** explicit-value metric (drift alarm if proxy ↑ / holdout ↓); **explore/exploit** (§7.3,
per-category Thompson with a pessimistic cold-start prior, ε decays, never raises volume); dismissal →
exponential-backoff per-category cooldown; **scheduler** on the Heartbeat (reflection threshold +
candidate→rank pass) → **once-daily digest** (default) + event-triggered real-time for time-critical
only; the **daily briefing fires automatically**. A test proves the objective is usefulness.
