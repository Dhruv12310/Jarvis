# Plan: Jarvis — Phase 3 (Voice + UI)

Source-of-truth: `SPEC.md` (this phase) + `CLAUDE.md` invariants + `docs/Jarvis_Core_Spec.md` (§3
Voice/UI are the *delivery surface* that feeds the Core; §5.5 `Suggestion.channel`; §8 Brain/on-demand).
One vertical slice per commit. The load-bearing rule: **thin front-ends over one shared facade** — the
GUI and voice never reimplement core logic. Phase 0–2 plans are in git history.

```
Slice 1   App-service facade   JarvisService over the existing core; refactor CLI onto it (no behavior change)
        |
Slice 2   UI shell             Flet window + chat + the Jarvis feed (briefing as a card) over the facade
Slice 3   Shortcut buttons     common actions -> facade calls -> results into the feed
        |  >>> Checkpoint: UI HALF is a complete, shippable milestone (pressure-release valve) <<<
Slice 4   STT (push-to-talk)   record -> faster-whisper -> text enters the facade
Slice 5   TTS + full loop      Piper speaks the answer; record->transcribe->answer->speak
```

Order: Slice 1 first (unblocks every front-end). Slices 2–3 (UI half) and 4–5 (voice half) are largely
independent after Slice 1; both touch `__main__.py` + the facade, so serialize there. **If voice drags,
ship the UI half (1–3) and do voice as a clean follow-on.**

Dependency graph:
- Slice 1 (facade) ← nothing; blocks all.
- Slices 2, 3 ← Slice 1 (UI renders facade results).
- Slice 4 ← Slice 1 (STT feeds `facade.ask`).
- Slice 5 ← Slice 4 (speaks the answer; completes the loop).

---

## Task List

### Slice 1 — Application-service facade  [THE unblocker; no new behavior]
**Description:** Extract a single `JarvisService` that composes the existing core and exposes capability
methods returning **structured results** (not prints). Move signal capture into it (stamp `source`).
Refactor the CLI onto it with **no user-facing behavior change**.

**The bar (user-confirmed):** this touches working Phase 0–2 code, so "refactor" is not a license for
drift — **every existing test stays green and the CLI behaves identically.** No regressions sneak in.

**Acceptance:**
- [ ] `jarvis/results.py`: `AskResult(text, grounded, cached)`, `AgendaResult(events, connected)`.
  (Goals/memory return the existing `Goal`/`MemoryRecord`; briefing returns `str`.)
- [ ] `jarvis/service.py`: `JarvisService(*, orchestrator, knowledge, store, memory, signals, source)`
  with `ask`, `briefing`, `add_goal`, `list_goals`, `complete_goal`, `agenda`, `remember`, `recall`.
  Each method does the existing work and **emits exactly one `SignalEvent`** with `{**payload, "source"}`.
  The briefing's best-effort calendar+digest gathering moves here (so GUI/voice inherit the resilience).
- [ ] `jarvis/cli.py`: `run()` builds `JarvisService(source="cli")`; `_loop`/`_handle_*` call facade
  methods and render (print) the results; the per-turn `signals.emit` is removed (the facade emits now).
- [ ] CLI observable behavior preserved: same prints for ask / `:goal*` / `:cal` / `:brief` / memory;
  REPL still survives backend errors; key redaction intact.

**Verification:** `tests/test_service.py` — with a **faked core**, each method returns the right result
type AND appends exactly one signal stamped `source`. `tests/test_cli.py` updated to the facade path,
asserting the same observable output. Full suite green; `ruff` clean.
**Files:** `jarvis/results.py`, `jarvis/service.py`, `jarvis/cli.py`, `tests/test_service.py`,
`tests/test_cli.py` (+ signal-emission tests updated). **Scope:** L.
**Commit:** `feat(service): JarvisService facade; refactor CLI onto it (no behavior change)`

### ▸ Checkpoint: one code path
- [ ] CLI runs entirely through `JarvisService`; signals emit once per interaction with `source="cli"`.

### Slice 2 — UI shell over the facade  [Flet — CONFIRMED]
**Source-driven first:** verify the current **Flet** API for the pinned version (`ft.app`/`Page`, a
scrolling `ListView`/`Column` of `Card`s, a chat `TextField` + send, `page.update()` model).

**Acceptance:**
- [ ] (decided) UI framework is **Flet**; our-own-web-UI fallback kept open but not built now.
- [ ] `pyproject` += `flet` (pinned 0.80.x); approved-deps set += `flet`; boundary test: `flet` imported
  only under `jarvis/ui/`.
- [ ] `jarvis/ui/feed.py`: a `Card`/`Feed` model + render; `post_card(card)` appends to the feed
  (the receive surface Phase 5 will push into — **no generation here**).
- [ ] `jarvis/ui/app.py`: Flet window with (a) a **chat view** (input + message list) and (b) the
  **Jarvis feed** (scrolling cards). On launch it renders **today's briefing as a card** via
  `service.briefing()`. Sending a chat message calls `service.ask()` and renders the answer.
- [ ] `jarvis/__main__.py`: `python -m jarvis ui` builds `JarvisService(source="gui")` + launches the app.

**Verification:** `tests/test_ui_feed.py` — the pure feed/card model + the view-model dispatch
(message → `service.ask` → card) tested with a **faked facade, without launching Flet**; `post_card`
appends. Manual: `python -m jarvis ui` shows the window, the briefing card, and working chat.
**Files:** `pyproject.toml`, `jarvis/ui/{__init__,app,feed}.py`, `jarvis/__main__.py`,
`tests/test_ui_feed.py`, `tests/test_boundaries.py`. **Scope:** L.
**Commit:** `feat(ui): desktop GUI shell over the facade (chat + Jarvis feed)`

### Slice 3 — Shortcut buttons
**Acceptance:**
- [ ] Buttons in `ui/app.py`: **Briefing**, **Today's calendar**, **Markets/News/HN** (a preset
  `service.ask`), **Add goal** (input → `service.add_goal`). Each calls a facade method and renders the
  result into the feed/chat (calendar → a card listing today's events; goal → a confirmation card).
- [ ] Button→action dispatch is a small pure mapping (testable without Flet).

**Verification:** `tests/test_ui_feed.py` extended — each shortcut invokes the right facade method and
posts the expected card (faked facade). Manual: each button works and shows results.
**Files:** `jarvis/ui/app.py`, `tests/test_ui_feed.py`. **Scope:** M.
**Commit:** `feat(ui): shortcut buttons for common actions`

### ▸ Checkpoint: UI HALF SHIPPABLE (pressure-release valve) — HARD STOP (user-confirmed)
- [ ] Chat + feed (briefing card) + shortcuts all work **end-to-end** over the facade; CLI unchanged;
  tests green. **Honor this as a real stop:** the text GUI must work before voice starts — do NOT slide
  straight into STT. **Decision point:** proceed to voice (4–5), or ship the UI half now as the milestone.

### Slice 4 — STT (push-to-talk voice input)
**Source-driven first:** verify `faster-whisper` `WhisperModel(size).transcribe(...)` + model name
(`large-v3-turbo`) and `sounddevice` capture against current docs.

**Acceptance:**
- [ ] `pyproject` += `faster-whisper`, `sounddevice`, `numpy`; approved-deps += them; boundary test:
  these imported only under `jarvis/voice/`.
- [ ] `jarvis/voice/stt.py`: `SpeechToText` (ABC) + `FasterWhisperSTT` (the ONLY faster-whisper importer);
  `transcribe(audio) -> str`. Model size from `config`.
- [ ] `jarvis/voice/audio.py`: push-to-talk recorder (`sounddevice`) — capture mic audio while held.
- [ ] `jarvis/voice/loop.py`: `record -> stt.transcribe -> service.ask -> render text` (TTS in Slice 5).
- [ ] `jarvis/__main__.py`: `python -m jarvis voice` runs the push-to-talk loop (text out for now).
- [ ] `config`: STT model size (default `large-v3-turbo`).

**Verification:** `tests/test_voice_loop.py` — `record→stt→facade.ask` wired with a **fake STT** + faked
facade (no audio/models); asserts the transcript enters `service.ask` and the answer is returned.
`tests/test_stt.py` `@integration` — real `faster-whisper` transcribes a tiny fixed WAV to the expected
text; **skips** when the model/audio is absent. Manual: push-to-talk asks a real question.
**Files:** `pyproject.toml`, `jarvis/voice/{__init__,stt,audio,loop}.py`, `jarvis/__main__.py`,
`jarvis/config.py`, `tests/test_voice_loop.py`, `tests/test_stt.py`, `tests/test_boundaries.py`. **Scope:** L.
**Commit:** `feat(voice): push-to-talk STT into the pipeline`

### Slice 5 — TTS + full listen→answer→speak loop
**Source-driven first:** verify the current `piper` Python/CLI invocation + voice model
(`en_US-lessac-high`) and playback.

**Acceptance:**
- [ ] `pyproject` += `piper-tts`; approved-deps += it; boundary test: `piper` only under `jarvis/voice/`.
- [ ] `jarvis/voice/tts.py`: `TextToSpeech` (ABC) + `PiperTTS` (the ONLY piper importer);
  `speak(text)` synthesizes + plays locally. Voice/model from `config`. (Kokoro is a future swap.)
- [ ] `jarvis/voice/loop.py`: full `record -> transcribe -> service.ask -> tts.speak`.
- [ ] `config`: TTS voice/model.

**Verification:** `tests/test_voice_loop.py` updated — a **fake TTS** asserts the answer text is spoken
after `service.ask`. `tests/test_tts.py` `@integration` — real Piper produces non-empty audio for a
short string; **skips** when the model is absent. Manual: full spoken loop (speak → hear the answer).
**Files:** `pyproject.toml`, `jarvis/voice/{tts,loop}.py`, `jarvis/config.py`, `tests/test_voice_loop.py`,
`tests/test_tts.py`, `tests/test_boundaries.py`. **Scope:** M.
**Commit:** `feat(voice): local TTS; full listen-answer-speak loop`

### ▸ Checkpoint: Phase 3 complete
- [ ] UI (chat + feed + shortcuts) and voice (push-to-talk → STT → pipeline → TTS) both work; CLI
  unchanged; signals captured for all modalities; audio/private data stay local (boundary check); offline
  tests green, STT/TTS integration gated. Proceed `/test` → `/review` → `/code-simplify` → `/ship`,
  recording learnings to `docs/DECISIONS.md`.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| UI framework balloons / Flet pre-1.0 churn | High | Pin Flet; keep UI thin behind a view seam; ship the UI half (1–3) standalone; web fallback documented |
| Voice stack (models/audio) drags the phase | High | Voice is a separate half (4–5); integration-gated + size in config; ship UI half if voice slips |
| A front-end reimplements core logic | High | Single `JarvisService`; boundary tests confine flet/voice libs; no business logic in ui/ or voice/ |
| Audio device variability across machines | Med | `sounddevice` (cross-platform); STT/TTS tests gated/skipped when no device/model (like OAuth) |
| Model weights download = perceived egress | Med | One-time public-weight fetch (documented, pinned); audio/transcripts never leave; assert no data egress |
| CLI refactor regresses behavior | Med | Facade returns data; CLI tests assert unchanged observable output; full suite green before commit |
| Smuggling Phase 5 in (autonomous cards) | Med | Feed is receive/display only (`post_card`); NO generation/ranking/reflection in Phase 3 |

## Open Questions — all RESOLVED with the user
- **OQ1 (UI framework)** — **Flet** (confirmed); our-own web UI kept as a later fallback.
- OQ2 STT — faster-whisper `large-v3-turbo` (size in config). OQ3 TTS — Piper baseline, Kokoro swap later.
  OQ4 activation — push-to-talk (wake-word deferred). OQ5 split — UI half independently shippable; the
  Slice-3 checkpoint is a hard stop. All verified per slice via source-driven-development.

## Parallelization
- Slice 1 is the barrier (everything depends on the facade).
- After Slice 1: UI half (2→3) and voice half (4→5) are independent tracks; both touch `__main__.py` +
  the facade surface, so serialize edits there. The UI half is the shippable milestone if voice slips.
