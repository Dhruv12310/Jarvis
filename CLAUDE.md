# Jarvis — Project Constitution (CLAUDE.md)

> Read this every session before doing anything. It is the source of truth for how this repo works. Keep it lean.

## How to work here (read first)

Behavioral guardrails:
- **Think before coding.** Don't assume — surface tradeoffs and ask when the path is unclear. Restate the goal before building.
- **Simplicity first.** Write the minimum code that solves the task. No speculative abstractions, no "while I'm here" extras.
- **Surgical changes.** Touch only what the task needs. Do not refactor unrelated code.
- **Goal-driven.** Define the success criteria up front, then work toward them.

Process:
- Use the agent-skills lifecycle for every unit of work: `/spec` → `/plan` → `/build` → `/test` → `/review` → `/code-simplify` → `/ship`.
- Build **one phase at a time** (see Build order). Do not build ahead of the current phase.
- A phase is done only when `/test` and `/review` pass. Then start the next.
- Run `mulch prime` at session start; record conventions/patterns/decisions/failures with Mulch when work completes.

## What Jarvis is

A local-first personal AI assistant that runs primarily on the user's own hardware for privacy and zero token cost, escalating to a cloud LLM only as a controlled exception. Capabilities (built in phase order): knowledge/research, calendar + daily briefings + goals, voice conversation, personal finance, and proactive suggestions that learn the user's patterns.

## Architecture invariants (do NOT violate)

- **Three zones.** Brain = RTX 5080 rig, on-demand (inference, voice, orchestration). Heartbeat = HP Pavilion, always-on 24/7 (scheduler, collectors, data stores, queue, backend). Cloud = escalation only.
- **Three compute tiers.** Tier 0 = deterministic engines; Tier 1 = local LLM as conductor (understand → route → summarize → converse); Tier 2 = cloud LLM (escalation: hard reasoning / large context / explicit ask). The LLM delegates DOWN to engines and escalates UP to cloud.
- **Deterministic-first.** If a task can be done in code, it is NOT given to an LLM. Finance math, date/calendar logic, market formulas, ranking, classification, and retrieval are deterministic. The LLM only phrases results.
- **Trust boundary.** Nothing private leaves the machine. Only the Model Router (after PII stripping) and the Collectors (public data only) may cross to the cloud.
- **Storage split.** Structured/relational data goes through the `StructuredStore` interface (SQLite is the default implementation; a JSON-tree implementation may be validated later behind the same interface). Semantic/episodic memory goes in a vector store. Two stores because there are two query types; do not collapse them.
- **Proactivity objective.** The proactivity ranker optimizes for USEFULNESS (saved time / advanced a goal / prevented a miss). NEVER for engagement or time-on-app.

## Build order (one phase at a time)

0. **Foundation** — local model (Ollama) + thin orchestrator + StructuredStore/SQLite + vector-store skeletons + CLI chat. *Prove the brain works.*
1. **Knowledge** — collectors (market / news / YC-HN) + summarize pipeline.
2. **Organization** — calendar + daily briefing + project/goal memory. **Turn on signal capture here.**
3. **Voice + UI** — STT/TTS + desktop UI with shortcut buttons + the delivery surface ("Jarvis feed").
4. **Finance** — Plaid (US, free tier) → tracking → local analysis (deterministic math).
5. **Proactivity** — reflection + user model + two-stage recommender + feedback loop. (Jarvis Core, full.)
6. **Mobile** — Android companion: finance + spam-risk scoring (NOT stranger name-lookup; no clean legal API exists).

Sequencing rule: signal capture (Phase 2) must precede the learning logic (Phase 5) that consumes it.

## Specs (source of truth — reference before each phase)

- `docs/Jarvis_Core_Spec.md` — the memory / learning / proactivity subsystem (Phases 2, 3, 5). Read §3–§4 for boundaries and the deterministic-vs-LLM split before touching the Core.
- `docs/ARCHITECTURE.md` — full system architecture (to add).

Generate a per-phase implementation spec with `/spec`, referencing the relevant doc above. Do not invent design that contradicts these specs; if a spec is unclear, ask.

## Stack & conventions

- Python; lightweight, no heavy agent frameworks (the orchestrator is custom and small).
- Local LLM via Ollama (Qwen3-14B or Phi-4). Vector store: Chroma or Qdrant. Cache: Redis. Introduce each dependency only when its phase needs it — not before.
- Commit format: `feat|fix|chore(scope): description`.
- Build / test / lint commands: _(fill in once they exist)_.

## Memory (Mulch)

`mulch prime` before starting work. Record learnings (conventions, patterns, decisions, failures) when work completes so the next session inherits them. _(The `mulch onboard` usage section is appended below.)_

<!-- mulch:start -->
## Project Expertise (Mulch)
<!-- mulch-onboard:v0.10.6 -->

This project uses [Mulch](https://github.com/jayminwest/mulch) v0.10.6 for structured expertise management.

**At the start of every session**, run:
```bash
ml prime
```

Injects project-specific conventions, patterns, decisions, failures, references, and guides into
your context. Run `ml prime --files src/foo.ts` before editing a file to load only records
relevant to that path (per-file framing, classification age, and confirmation scores included).

For monolith projects where dumping every record wastes context, set
`prime.default_mode: manifest` in `.mulch/mulch.config.yaml` (or pass `--manifest`) to emit a
quick reference + domain index. Agents then scope-load with `ml prime <domain>` or
`ml prime --files <path>`.

**Before completing your task**, record insights worth preserving — conventions discovered,
patterns applied, failures encountered, or decisions made:
```bash
ml record <domain> --type <convention|pattern|failure|decision|reference|guide> --description "..."
```

Evidence auto-populates from git (current commit + changed files). Link explicitly with
`--evidence-seeds <id>` / `--evidence-gh <id>` / `--evidence-linear <id>` / `--evidence-bead <id>`,
`--evidence-commit <sha>`, or `--relates-to <mx-id>`. Upserts of named records merge outcomes
instead of replacing them; validation failures print a copy-paste retry hint with missing fields
pre-filled.

Run `ml status` for domain health, `ml doctor` to check record integrity (add `--fix` to strip
broken file anchors), `ml --help` for the full command list. Write commands use file locking and
atomic writes, so multiple agents can record concurrently. Expertise survives `git worktree`
cleanup — `.mulch/` resolves to the main repo.

`ml prune` soft-archives stale records to `.mulch/archive/` instead of deleting them; pass
`--hard` for true deletion. Restore an archived record with `ml restore <id>`. Do not read
`.mulch/archive/` directly — those records are stale by definition. If you need historical
context, run `ml search --archived <query>`.

### Before You Finish

If you discovered conventions, patterns, decisions, or failures worth preserving during
this session, record them before closing:

```bash
ml learn                                                                    # see what files changed
ml record <domain> --type <convention|pattern|failure|decision|reference|guide> --description "..."
ml sync                                                                     # validate, stage, commit
```

Skip if no insight surfaced. Unrecorded learnings are lost; ritual filler records are also noise.
<!-- mulch:end -->
