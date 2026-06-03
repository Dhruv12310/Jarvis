# Spec: Jarvis — Phase 3 (Voice + UI)

> Per-phase implementation spec for the **active** phase. Phases 0–2 are shipped; their specs live in
> `docs/specs/` and git history. Design source-of-truth: `CLAUDE.md` (invariants) and
> **`docs/Jarvis_Core_Spec.md`** (§3 places Voice/UI as the *delivery surface* that FEEDS the Core, not
> part of it; §5.5 `Suggestion.channel = feed|voice|notification`; §8 zones — Voice/UI run on the
> **Brain**, on-demand). Phase 0–2 learnings + deferred decisions: `docs/DECISIONS.md`.

## Objective

Give Jarvis a **face and a voice**. A local desktop UI where I can chat (same grounded, cited Q&A as
the CLI), see my daily briefing as a card in a **"Jarvis feed,"** and trigger common actions with
shortcut buttons — plus a **local voice loop**: I push a key, speak, Jarvis transcribes locally,
answers through the existing pipeline, and speaks the answer back.

This phase adds **NO new intelligence.** It is a presentation + I/O layer over the existing core. The
only model calls are the ones that already exist (routing, summarizing, briefing) plus the new
**local** STT and TTS. Reflection, user model, ranking, and autonomous card generation are Phase 5.

**Who it's for:** the single user (dbhatt24), now at a desktop GUI and by voice, in addition to the CLI.

### The load-bearing constraint (read twice)

The GUI and voice loop are **thin front-ends** over the existing orchestrator / knowledge pipeline /
memory / briefing / goals / calendar. They call the **same application code the CLI calls** — they
never reimplement or duplicate that logic. To make that durable, this phase introduces a single
**application-service facade** (`JarvisService`) that exposes the existing capabilities; the CLI is
refactored onto it (no user-facing behavior change), and the GUI + voice loop are additional front
doors to the *same* facade. Get this right and Phase 3 is just new front doors; get it wrong and it's
a rewrite.

### Assumptions (correct me before I build)

1. **One facade, three front-ends.** A new `jarvis/service.py::JarvisService` composes the existing
   backends (orchestrator, knowledge, store, memory, calendar, briefing, signals) and exposes
   capability methods that **return structured results** (dataclasses) instead of printing. CLI, GUI,
   and voice all call it and render in their own way. No business logic leaves the facade/core.
2. **Signal capture moves into the facade.** Today the CLI emits one `SignalEvent` per turn; that
   emission moves *into* the facade so **every modality** (CLI/GUI/voice) is captured automatically and
   consistently, stamped with its `source` ("cli"|"gui"|"voice"). Phase 5's history then covers all
   modalities for free. User-facing CLI behavior is unchanged; the signal-log shape is unified (re-tested).
3. **UI framework = Flet** (CONFIRMED with the user). Python-only, Flutter-based (a real path to the
   Phase 6 Android companion), card feed + chat + buttons are first-class, packages to a desktop app.
   Pre-1.0 (0.80.x) churn is mitigated by pinning the version and keeping the UI thin behind our own
   small view seam. **Fallback (kept open):** switch to our own local web UI (FastAPI + htmx) later if
   Flet proves rough — the facade makes the swap cheap.
4. **STT = faster-whisper, model `large-v3-turbo`** on the Brain (RTX 5080, 16 GB — ample; ~0.5–2 s
   behind speech). Behind a `SpeechToText` seam; the model size is config so it can drop to `small`/`base`
   for lower latency. Models download once from HuggingFace (public weights) and run **fully local**
   thereafter; **audio never leaves the machine.**
5. **TTS = Piper** (snappy, ONNX, lowest latency) as the baseline behind a `TextToSpeech` seam; **Kokoro-82M**
   (higher naturalness, Apache-2.0) is the swappable upgrade. Local only; **audio never leaves.**
6. **Activation = push-to-talk** (press a key/button to record) for Phase 3. Always-on wake-word is an
   explicit **stretch/deferred** item; if ever attempted, VAD + wake-word run locally and no audio leaves.
7. **The feed is a receive/display surface only.** It renders the briefing and answers as cards and
   exposes a `post_card(...)` entry point **built to receive** pushed cards, so Phase 5 can later push
   `Suggestion`s into it. Phase 3 builds the surface; it generates **no** autonomous cards.
8. **CLI keeps working unchanged.** The new front-ends are additive; `python -m jarvis` is identical.

## Trust boundary (refined for local audio)

Phase 2 added a private *inbound* path (calendar). Phase 3 adds **local audio I/O** and a GUI — both
**stay on the machine**:

- STT and TTS are **local models on the Brain**; **microphone audio and transcripts never leave the
  machine**, and synthesized speech is produced locally. No cloud speech service, ever.
- The only outbound calls remain the existing **public connectors** (markets/news/HN) and the
  authenticated **calendar read** (Phase 2). The GUI/voice add **zero** new egress of private data; they
  route everything through the facade, which uses those same paths.
- Model weights (whisper, piper voice) download once from public repos — a one-time fetch of public
  artifacts (like a connector fetching public data), not data egress. Documented; pinned; offline after.
- Enforced by tests: audio/voice libs imported only under `jarvis/voice/`; the UI toolkit only under
  `jarvis/ui/`; no new `httpx`/socket egress outside `connectors/`; STT/TTS classes make no network call.

## Tech Stack

| Concern | Choice | Why |
|---|---|---|
| Application facade | `jarvis/service.py::JarvisService` | One code path for CLI/GUI/voice; returns structured results; emits signals |
| Desktop UI | **Flet** (pinned 0.80.x) | Python-only, Flutter-based (Phase 6 path), card feed + chat + buttons native; packages to desktop |
| STT (local) | **faster-whisper** `large-v3-turbo` (CTranslate2) | Fast + accurate on the 5080; local; size swappable; behind `SpeechToText` seam |
| TTS (local) | **Piper** (ONNX) baseline; Kokoro-82M upgrade | Snappy/low-latency; local; quality swappable behind `TextToSpeech` seam |
| Audio I/O | `sounddevice` (+ `numpy`) | Cross-platform mic capture + playback; small, well-supported |
| Routing / phrasing | existing Ollama `LLMClient` | LLM only does the pre-existing routing/summarizing/briefing — no new reasoning |
| Tests | `pytest` (+ faked core for UI/facade; gated integration for STT/TTS) | Offline-first; voice gated on models+audio like OAuth was gated |

**New runtime deps (introduced per slice, never before):** `flet` (UI slice), `faster-whisper` +
`sounddevice` + `numpy` (STT slice), `piper-tts` (TTS slice). Each is added to `pyproject` *and* the
approved-deps boundary set in the slice that needs it. **No heavyweight agent/web frameworks.**

## Commands

```bash
python -m jarvis                 # CLI (unchanged) — now backed by JarvisService
python -m jarvis ui              # launch the desktop GUI (chat + Jarvis feed + shortcut buttons)
python -m jarvis voice           # push-to-talk voice loop (listen -> pipeline -> speak); STT+TTS local
python -m jarvis calendar-auth   # (Phase 2) one-time Google Calendar OAuth
python -m jarvis selftest        # DoD self-test (offline-safe parts; voice/UI smoke where models present)

pytest -q                        # offline: facade + UI logic with the core faked; STT/TTS skipped
pytest -q -m integration         # live: STT/TTS with real local models + audio when present (else skip)
ruff check . ; ruff format --check .
```

## Project Structure

```
jarvis/
  service.py          # JarvisService facade: ask/briefing/goals/agenda/memory; returns results; emits signals
  results.py          # AskResult/BriefingResult/... structured return types shared by all front-ends
  cli.py              # REFACTORED onto JarvisService; same commands + prints; behavior unchanged
  ui/
    __init__.py
    app.py            # Flet app: window, chat view, the Jarvis feed (card list), shortcut buttons
    feed.py           # Feed/Card model + render; post_card(card) receive surface (Phase 5 will push here)
    (Flet is imported ONLY under ui/)
  voice/
    __init__.py
    stt.py            # SpeechToText seam (ABC) + FasterWhisperSTT (the ONLY faster-whisper importer)
    tts.py            # TextToSpeech seam (ABC) + PiperTTS (the ONLY piper importer)
    audio.py          # mic capture + playback (sounddevice); push-to-talk recorder
    loop.py           # push-to-talk loop: record -> stt -> JarvisService.ask -> tts.speak
  __main__.py         # + `ui` and `voice` subcommands
  (signals/, memory/, calendar/, stores/, knowledge/, briefing.py, orchestrator.py — unchanged core)
tests/
  test_service.py     # facade returns correct results + emits a signal per call (core faked)
  test_cli.py         # updated: CLI delegates to the facade; same observable behavior
  test_ui_feed.py     # deterministic feed/card render + dispatch + shortcut actions (Flet not launched)
  test_voice_loop.py  # loop wiring with fake STT/TTS + faked facade (no audio, no models)
  test_stt.py / test_tts.py   # @integration: real models, skip when model/audio absent
  test_boundaries.py  # extended: flet only under ui/, voice libs only under voice/, no new egress
```

## Code Style

The facade owns composition; front-ends own rendering only. Results are data, not printed strings.

```python
# results.py — structured returns so every front-end renders the same facts its own way.
@dataclass(frozen=True)
class AskResult:
    text: str
    grounded: bool        # True = knowledge pipeline (cited); False = labeled plain chat
    cached: bool

# service.py — the ONE place the core is composed. Each method returns data AND emits a SignalEvent.
class JarvisService:
    def __init__(self, *, orchestrator, knowledge, store, memory, signals, source: str): ...
    def ask(self, text: str) -> AskResult: ...           # knowledge route -> grounded, else chat
    def briefing(self) -> str: ...                        # deterministic assembly + LLM phrasing
    def add_goal(self, text: str) -> Goal: ...
    def list_goals(self) -> list[Goal]: ...
    def complete_goal(self, goal_id: int) -> Goal: ...
    def agenda(self) -> list[CalendarEvent]: ...          # today; [] if calendar not connected
    def remember(self, text: str) -> MemoryRecord: ...
    def recall(self, query: str) -> list[MemoryRecord]: ...
    # every method wraps its work + signals.emit(kind, {**payload, "source": self._source})
```

```python
# voice/stt.py + tts.py — model toolkits hidden behind seams (like StructuredStore/Connector).
class SpeechToText(ABC):
    @abstractmethod
    def transcribe(self, audio) -> str: ...
class TextToSpeech(ABC):
    @abstractmethod
    def speak(self, text: str) -> None: ...   # synthesize + play locally
```

Conventions (carry forward): type hints, frozen dataclasses for value objects, `ABC`/`Protocol` seams,
one config location, conventional commits (no em-dashes, no attribution), ruff clean, commit per slice.
No business logic in `ui/` or `voice/` — they call the facade and render/IO only.

## Testing Strategy

- **Facade (unit):** with the core **faked**, each `JarvisService` method returns the right result type
  and **emits exactly one `SignalEvent`** stamped with `source`. Proves the single-code-path contract.
- **CLI (unit):** the refactored CLI delegates to the facade and preserves observable behavior (same
  prints for ask/goals/cal/brief; REPL still survives backend errors; key redaction intact).
- **UI logic (unit):** feed/card render, command dispatch, and shortcut-button → facade-call mapping are
  unit-tested **without launching Flet** (test the pure view-model/dispatch, faked facade). `post_card`
  appends a card to the feed surface.
- **Voice loop (unit):** `record -> stt -> facade.ask -> tts.speak` wired with **fake STT/TTS** and a
  faked facade — no audio, no models. Asserts the transcript enters the pipeline and the answer is spoken.
- **STT/TTS (`@integration`):** real `faster-whisper` / `piper` with real audio; **skip** when the model
  or an audio device is absent (exactly how keyed connectors skip without keys and calendar skips without
  OAuth). A tiny fixed WAV → STT returns expected text; TTS produces non-empty audio.
- **Boundaries (extended):** `flet` imported only under `ui/`; `faster_whisper`/`piper`/`sounddevice`
  only under `voice/`; no new `httpx`/socket egress outside `connectors/`; STT/TTS make no network call.

## Boundaries

- **Always:**
  - All three front-ends go through `JarvisService`; **no business logic in `ui/` or `voice/`.**
  - STT, TTS, and the UI sit behind seams so the model/toolkit is swappable.
  - Every interaction (CLI/GUI/voice) emits a `SignalEvent` (now via the facade), stamped with `source`.
  - Audio + transcripts stay on the machine; only the existing public connectors + calendar read go out.
  - The feed is display/receive only (`post_card`), built to accept Phase 5 pushes.
  - `pytest` + `ruff` before each commit; conventional commits; commit per slice; CLI stays green throughout.
- **Ask First:**
  - Any dependency beyond the per-slice additions (`flet`; `faster-whisper`+`sounddevice`+`numpy`; `piper-tts`).
  - Changing the `JarvisService` facade surface once front-ends depend on it.
- **Never:**
  - Add new intelligence (reflection, user model, ranking, feedback, autonomous card generation — Phase 5);
    finance (Phase 4); the mobile companion (Phase 6); cloud escalation / Model Router.
  - Use ANY cloud STT/TTS or cloud UI service; let audio or private data leave the machine.
  - Reimplement core logic inside `ui/` or `voice/`; break or change the CLI's behavior.

## Success Criteria (Definition of Done — testable)

1. **Desktop UI launches** (`python -m jarvis ui`); I can chat in it and get the **same grounded, cited
   answers** as the CLI (same facade path).
2. **Feed** shows today's **briefing as a card**; answers also render as cards/messages.
3. **Shortcut buttons** (briefing, today's calendar, a markets/news/HN query, add-goal) trigger their
   actions via the facade and show results in the feed/chat.
4. **Push-to-talk:** I press to record, speak a question → **local STT** transcribes → the existing
   pipeline answers → **local TTS** speaks it back.
5. **CLI still works unchanged.**
6. **Voice/UI interactions produce `SignalEvent`s** like CLI interactions (stamped with `source`).
7. **No audio/private data leaves the machine:** a boundary check confirms STT/TTS are local and only the
   existing public connectors (+ calendar read) make outbound calls.
8. `pytest -q` passes fully offline (facade/UI/voice-loop with the core + STT/TTS faked); `-m integration`
   exercises real STT/TTS when models+audio are present (else skips); `selftest` PASS; `ruff` clean.

## Decisions (to confirm with the user — OPEN QUESTIONS resolved with recommendations)

1. **UI framework → Flet (CONFIRMED).** Python-only; Flutter-based (eases the Phase 6 Android
   companion); first-class cards/chat/buttons; packages to desktop; one language (highest CC reliability).
   Risk: pre-1.0 (0.80.x) API churn — mitigated by pinning + a thin UI seam. **Fallback kept open:**
   switch to our own local web UI (FastAPI + htmx) later if Flet proves rough; the facade makes it cheap.
2. **STT → faster-whisper `large-v3-turbo`** on the 5080 (size in config; can drop to `small`/`base`).
3. **TTS → Piper** (snappy baseline); Kokoro-82M swappable behind the seam.
4. **Activation → push-to-talk** baseline; always-on wake-word deferred (stretch).
5. **Phase split / pressure-release valve (TAKE SERIOUSLY).** Voice and UI are largely independent tracks.
   Slices 1–3 (facade + UI shell + shortcuts) are the **UI half** and are **independently shippable** — a
   complete, usable text GUI. Slices 4–5 (STT, then TTS) are the **voice half**, a clean follow-on. If
   voice drags, **ship the UI half** as a milestone and do voice separately; a working text UI beats a
   half-built voice loop bolted to nothing.
6. **`SPEC.md` is the Phase 3 spec**; a copy is kept at `docs/specs/phase-3.md`.

## Build-time verifications (source-driven-development, at the start of the relevant slice)

- **UI slice:** verify the current Flet API (app entry/`ft.app`, `Page`, the chat input + scrolling
  `ListView`/`Column` of `Card`s, buttons, async/update model) against the official Flet docs for the
  pinned version before building the shell.
- **STT slice:** verify the current `faster-whisper` `WhisperModel(...).transcribe(...)` API + model names
  (`large-v3-turbo`) and `sounddevice` capture against official docs.
- **TTS slice:** verify the current `piper` Python/CLI invocation + voice model files (e.g.
  `en_US-lessac-high`) and playback against official docs.

## Build Order (for /plan to slice — biggest phase yet; slice for independent shippability)

1. **Application-service facade** — extract `JarvisService` + result types; move signal capture into it
   (stamp `source`); **refactor the CLI onto it** with no behavior change; tests green. *Unblocks everything.*
2. **UI shell over the facade** — Flet window + chat view + the feed rendering the **briefing as a card** on
   real data. Prove the UI-over-core pattern; include the `post_card` receive surface (no generation).
3. **Shortcut buttons** — briefing / today's calendar / a markets-news-HN query / add-goal, wired to facade
   calls, results into the feed/chat. → **Checkpoint: UI half is a shippable milestone.**
4. **STT (push-to-talk)** — `SpeechToText` seam + faster-whisper + `sounddevice` capture; press-to-record →
   transcribe → text enters the facade (same pipeline). Integration-gated.
5. **TTS** — `TextToSpeech` seam + Piper + playback; speak the facade's answer; wire the full
   record→transcribe→answer→speak loop. Integration-gated. → **Checkpoint: voice half complete.**

Then `/test` → `/review` → `/code-simplify` → `/ship` per CLAUDE.md, recording learnings to `docs/DECISIONS.md`.
