# Phase 3 — TODO

Tracking list for `/build`. One vertical slice per commit. Full detail in `tasks/plan.md`.
**Thin front-ends over one shared facade** — GUI and voice never reimplement core logic.
(Phase 2 is shipped; its todo is in git history.)

---

## [x] Slice 1 — Application-service facade  ·  `feat(service): JarvisService facade; refactor CLI onto it (no behavior change)`
- [x] `results.py` — `AskResult(text, grounded, cached)`, `AgendaResult(events, connected)`
- [x] `service.py` — `JarvisService(*, orchestrator, knowledge, store, memory, signals, source)`: ask/briefing/add_goal/list_goals/complete_goal/agenda/remember/memories/recall (+ non-emitting recent_signals); each returns data + emits ONE signal stamped `source` (incl. on failure); briefing best-effort calendar+digest moved here
- [x] `cli.py` — refactored onto the facade (`source="cli"`); renders results; per-turn emit removed; `build_service(source)` shared for GUI/voice; behavior unchanged
- [x] Verify: `test_service.py` (faked core: result type + one stamped signal per call); `test_cli.py` updated (same observable output); 164 green; ruff clean; CLI smoke-tested

### ▸ Checkpoint: one code path — DONE (CLI runs entirely through JarvisService; signals stamped source="cli")

## [x] Slice 2 — UI shell over the facade  ·  `feat(ui): desktop GUI shell over the facade (chat + Jarvis feed)`   [Flet — confirmed]
- [x] (source-driven) verified Flet 0.85.2 API (ft.run, page.add/update, Card/ListView/TextField/Button/Markdown)
- [x] pyproject += `flet` (pinned <0.90); approved deps updated; boundary guard: flet only under `ui/`
- [x] `ui/feed.py` — Card/Feed model; `post_card(card)` receive surface (Phase 5 pushes here; no generation)
- [x] `ui/app.py` — Flet window: scrolling card feed + chat input; briefing as a card on launch; send → `service.ask`
- [x] `__main__.py` — `python -m jarvis ui` (builds `JarvisService(source="gui")`; never imports flet itself)
- [x] Verify: `test_ui_feed.py` (feed/controller with faked facade, no Flet launch); widgets smoke-built; 170 green
- [ ] **PENDING USER:** visual launch (`python -m jarvis ui`) — window + briefing card + chat work

## [x] Slice 3 — Shortcut buttons  ·  `feat(ui): shortcut buttons for common actions`
- [x] Buttons: Briefing / Today's calendar / Markets-News / Add goal → facade calls → results into the feed
- [x] Button→action dispatch is a pure controller mapping (testable without Flet)
- [x] Verify: `test_ui_feed.py` extended (each shortcut → right facade method + posted card); 176 green

### ▸ Checkpoint: UI HALF SHIPPABLE — HARD STOP (honoring user) — awaiting visual verify; then proceed to voice OR ship the UI half

## [ ] Slice 4 — STT (push-to-talk)  ·  `feat(voice): push-to-talk STT into the pipeline`
- [ ] (source-driven) verify faster-whisper `WhisperModel.transcribe` + `large-v3-turbo` + sounddevice capture
- [ ] pyproject += `faster-whisper`, `sounddevice`, `numpy`; approved deps updated; boundary guard: voice libs only under `voice/`
- [ ] `voice/stt.py` `SpeechToText` ABC + `FasterWhisperSTT`; `voice/audio.py` push-to-talk recorder; `voice/loop.py` record→stt→`service.ask`→text
- [ ] `__main__.py` `python -m jarvis voice`; `config` STT model size
- [ ] Verify: `test_voice_loop.py` (fake STT + faked facade: transcript enters `service.ask`); `test_stt.py` @integration (real model on a fixed WAV, skip if absent); manual

## [ ] Slice 5 — TTS + full loop  ·  `feat(voice): local TTS; full listen-answer-speak loop`
- [ ] (source-driven) verify piper invocation + voice model + playback
- [ ] pyproject += `piper-tts`; approved deps updated; boundary guard: piper only under `voice/`
- [ ] `voice/tts.py` `TextToSpeech` ABC + `PiperTTS` (synthesize + play); `voice/loop.py` full record→transcribe→`service.ask`→`tts.speak`; `config` TTS voice
- [ ] Verify: `test_voice_loop.py` (fake TTS asserts the answer is spoken); `test_tts.py` @integration (real piper non-empty audio, skip if absent); manual full loop

### ▸ Checkpoint: Phase 3 complete → `/test` → `/review` → `/code-simplify` → `/ship` → record learnings in docs/DECISIONS.md
