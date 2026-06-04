# Phase 5c — TODO (Feedback loop + explore/exploit + scheduler + auto-briefing)

Tracking list for `/build`. One vertical slice per commit. North star in `SPEC.md` / `docs/specs/phase-5b.md`.
**THE law: usefulness, never engagement (Core §8).** The reward measures GENUINE value (explicit helpful
/ acted-AND-corroborated), NEVER attention - `shown`/`ignored`/`dwell` are never positive; `acted` alone
is non-positive. Reward by value MAGNITUDE, not event count. Exploration changes WHICH slot fills, never
whether/volume. Deterministic-first; everything local. 5a + 5b shipped/committed.

---

## [ ] Slice 1 — Outcome capture + reward labeling  ·  `feat(proactivity): outcome capture and value-corroborated reward (§7.5/§8)`
- [ ] `stores` — `Outcome` value object + `outcomes` table + `save_outcome`/`get_outcomes` (raw SQL in sqlite)
- [ ] `proactivity/feedback.py` — pure `reward(result, *, corroborated=False)`: more_like_this>0, acted=+only if corroborated else 0, dismissed/less_like_this<0, ignored=0 (§8)
- [ ] `service.record_outcome(suggestion_id, result)` — persist + metadata-only `outcome` signal; `cli :rate <id> <result>`
- [ ] Verify: `test_feedback.py` (reward §8 semantics: acted-alone non-positive, dismissed negative, helpful positive) + outcome store round-trip

## [ ] Slice 2 — Feedback application (§7.5)  ·  `feat(proactivity): apply outcomes to the user model and learned ranker weights`
- [ ] `proactivity/feedback.py` — `apply_outcome(outcome, suggestion, model, weights, *, now, ...)`: positive → amplify goal-linked topic (confidence_after) + bump linked memory importance; negative → suppress topic; learned per-feature β multipliers nudged by reward×contribution (clamped); reward by magnitude not count
- [ ] `stores` — feedback weights get/save (a `{feature: multiplier}` row)
- [ ] `rank.py` — `usefulness` reads `config.beta_x * learned_multiplier_x`
- [ ] `service.record_outcome` — applies feedback after persisting
- [ ] Verify: `test_feedback.py` — positive on a feature raises its multiplier → ranking measurably shifts; acted-alone shifts nothing; dismissal decays the topic weight; a non-goal topic still can't be amplified (§8)

## [ ] Slice 3 — Explore/exploit + per-category cooldown (§7.3)  ·  `feat(proactivity): per-category value learning, bounded exploration, dismissal backoff`
- [ ] `proactivity/bandit.py` — per-category Beta(1,3) pessimistic posterior from outcomes (α=positives, β=negatives); `value_estimate(cat)`; `explore?(now, ε)` with ε decaying as total outcomes rise
- [ ] `rank.select` — exploit: down-weight chronically-dismissed categories by posterior; explore: occasionally swap an under-tried category's top candidate IN PLACE OF a proven one (never +1 slot); per-category exponential-backoff cooldown on consecutive dismissals (1→3→7 days) suppresses a category
- [ ] Verify: `test_bandit.py` + `test_rank.py` additions — exploration never raises the count past the cap; ε decays with outcome count; consecutive dismissals lengthen the cooldown

## [ ] Slice 4 — Scheduler + auto-briefing + holdout + the proof  ·  `feat(proactivity): heartbeat scheduler, auto-briefing, and the usefulness-not-engagement proof`
- [ ] `proactivity/scheduler.py` — pure `tick(service, now)`: reflect on threshold → run suggestions pass → deliver time-critical real-time else queue → at the digest hour deliver the daily digest + the auto-briefing (deferred from Phase 2); thin `run(service)` loop wrapper
- [ ] holdout explicit-value metric (rolling helpful-rate, never trained on) + a drift check (proxy ↑ while holdout ↓ → alarm); `python -m jarvis schedule`
- [ ] Verify: `test_scheduler.py` — tick reflects/surfaces/digests at the right times (injected now); **THE proof test: a `shown`/`ignored` outcome yields zero positive weight movement while `more_like_this` is positive — the objective is usefulness, not engagement**

### ▸ Checkpoint: 5c feature-complete → `/test` → multi-lens review (objective-drift lens) → `/code-simplify` → `/ship` → record learnings → **Phase 5 (desktop Jarvis) DONE**.
