# Phase 3 — TODO

Tracking list for `/build`. One vertical slice per commit. Full detail in `tasks/plan.md`.
**Thin front-ends over one shared facade** — GUI and voice never reimplement core logic.
(Phase 2 is shipped; its todo is in git history.)

---

## [ ] Slice 1 — Application-service facade  ·  `feat(service): JarvisService facade; refactor CLI onto it (no behavior change)`
- [ ] `results.py` — `AskResult(text, grounded, cached)`, `AgendaResult(events, connected)`
- [ ] `service.py` — `JarvisService(*, orchestrator, knowledge, store, memory, signals, source)`: ask/briefing/add_goal/list_goals/complete_goal/agenda/remember/recall; each returns data + emits ONE signal stamped `source`; briefing's best-effort calendar+digest moves here
- [ ] `cli.py` — refactor onto the facade (`source="cli"`); render results; drop the per-turn emit; behavior unchanged
- [ ] Verify: `test_service.py` (faked core: result type + one stamped signal per call); `test_cli.py` updated (same observable output); full suite green; ruff clean

### ▸ Checkpoint: one code path

## [ ] Slice 2 — UI shell over the facade  ·  `feat(ui): desktop GUI shell over the facade (chat + Jarvis feed)`   [Flet — confirmed]
- [ ] (source-driven) verify current Flet API for the pinned version
- [ ] pyproject += `flet` (pinned); approved deps updated; boundary guard: flet only under `ui/`
- [ ] `ui/feed.py` — Card/Feed model + render; `post_card(card)` receive surface (Phase 5 pushes here; no generation)
- [ ] `ui/app.py` — Flet window: chat view + Jarvis feed; briefing rendered as a card on launch; send → `service.ask`
- [ ] `__main__.py` — `python -m jarvis ui` (builds `JarvisService(source="gui")`)
- [ ] Verify: `test_ui_feed.py` (feed/card model + dispatch with faked facade, no Flet launch); manual launch

## [ ] Slice 3 — Shortcut buttons  ·  `feat(ui): shortcut buttons for common actions`
- [ ] Buttons: Briefing / Today's calendar / Markets-News-HN / Add goal → facade calls → results into the feed
- [ ] Button→action dispatch is a small pure mapping (testable without Flet)
- [ ] Verify: `test_ui_feed.py` extended (each shortcut → right facade method + posted card); manual

### ▸ Checkpoint: UI HALF SHIPPABLE (pressure-release valve) — proceed to voice OR ship the UI half now

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
