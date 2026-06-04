# Phase 5c — TODO (Feedback loop + explore/exploit + scheduler + auto-briefing)

Tracking list for `/build`. One vertical slice per commit. North star in `SPEC.md` / `docs/specs/phase-5b.md`.
**THE law: usefulness, never engagement (Core §8).** The reward measures GENUINE value (explicit helpful
/ acted-AND-corroborated), NEVER attention - `shown`/`ignored`/`dwell` are never positive; `acted` alone
is non-positive. Reward by value MAGNITUDE, not event count. Exploration changes WHICH slot fills, never
whether/volume. Deterministic-first; everything local. 5a + 5b shipped/committed.

---

## [x] Slice 1 — Outcome capture + reward labeling  ·  `feat(proactivity): outcome capture and value-corroborated reward (§7.5/§8)` (fb5c42a)
- [x] `stores` — `Outcome` + `outcomes` table + `save_outcome`/`get_outcomes`
- [x] `proactivity/feedback.py` — pure `reward(result, *, corroborated)`: helpful>0, acted=0 unless corroborated, dismissed/less<0, ignored=0 (§8)
- [x] `service.record_outcome` + metadata-only `outcome` signal; `cli :rate <id> <result>`
- [x] Verify: `test_feedback.py` reward §8 semantics + outcome round-trip

## [x] Slice 2 — Feedback application (§7.5)  ·  `feat(proactivity): apply outcomes to the user model and learned ranker weights` (ab8599b)
- [x] `feedback.apply_outcome` — positive amplifies goal-linked topic + driving features; negative suppresses; learned per-feature multipliers nudged by reward MAGNITUDE, clamped [0.5,2.0]
- [x] `stores` — Suggestion.topics + `get_suggestion` + feedback_weights row; `rank.usefulness` reads `beta * multiplier`; `service.record_outcome` applies
- [x] Verify: positive amplifies + reinforces; acted-alone moves nothing; dismissal suppresses+attenuates; non-goal stays 0 (§8); learned weights scale the score

## [x] Slice 3 — Explore/exploit + per-category cooldown (§7.3)  ·  `feat(proactivity): per-category value learning, bounded exploration, dismissal backoff` (a2cc149)
- [x] `proactivity/bandit.py` — per-category Beta(1,3) pessimistic posterior; deterministic UCB `category_multiplier`; exponential-backoff `cooldown_active`
- [x] `rank.select` — bandit RE-RANKS survivors (post-threshold) + drops dismissal-cooled categories; never adds a slot (§8); `stores` CategoryOutcome + join; EngineState + service load
- [x] Verify: `test_bandit.py` + `test_rank.py` — pessimistic prior; proven outranks dismissed; untried gets a lift; backoff lengthens; re-rank never exceeds the cap

## [x] Slice 4 — Scheduler + auto-briefing + holdout + the proof  ·  `feat(proactivity): heartbeat scheduler, auto-briefing, and the usefulness-not-engagement proof` (ea68e59)
- [x] `proactivity/scheduler.py` — pure `tick(service, now, state)`: reflect-if-due → suggestions pass → daily digest + auto-briefing at the digest hour; thin `run` loop; `python -m jarvis schedule`
- [x] `feedback.value_metric` holdout helpful-rate (never trained on); `service.value_report()` + `:value`
- [x] Verify: `test_scheduler.py` (reflect/surface each beat; digest once/day) + **THE capstone: an `ignored` outcome yields zero weight movement while `more_like_this` reinforces — usefulness, not engagement**

### ▸ Checkpoint: 5c feature-complete (all 4 slices committed) → full suite → review → push → **Phase 5 (desktop Jarvis) DONE**.
