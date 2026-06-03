"""The push-to-talk voice loop: record -> transcribe -> ask -> (optionally) speak.

`handle_turn` is the pure core (inject STT/TTS/service + audio), unit-tested with fakes.
`run_voice_loop` does the console + mic IO around it. The answer comes from the SAME `service.ask`
the CLI and GUI use - voice adds no intelligence, only I/O.
"""

from __future__ import annotations

from jarvis.service import JarvisService
from jarvis.voice.stt import SpeechToText


def handle_turn(service: JarvisService, stt: SpeechToText, audio, tts=None) -> str | None:
    """One turn: transcribe the audio, ask the pipeline, speak the answer if a TTS is given.

    Returns the answer text, or None when nothing was transcribed.
    """
    text = stt.transcribe(audio).strip()
    if not text:
        return None
    result = service.ask(text)
    if tts is not None:
        tts.speak(result.text)
    return result.text


def run_voice_loop(service: JarvisService, stt: SpeechToText, tts=None) -> None:
    from jarvis.voice.audio import record_until_enter

    print("Voice mode. Press Enter to talk, Enter again to stop. Ctrl-C to quit.")
    while True:
        try:
            input("\n[Enter to talk] ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        answer = handle_turn(service, stt, record_until_enter(), tts)
        print("jarvis> " + answer if answer is not None else "(heard nothing)")
