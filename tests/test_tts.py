"""Live TTS (gated integration): Piper synthesizes + plays without raising.

OFF by default (set JARVIS_VOICE_INTEGRATION=1) and skipped when the Piper voice file is absent -
the same gating the keyed-connector / OAuth / STT integration tests use. Run on the Brain.
"""

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

if not os.environ.get("JARVIS_VOICE_INTEGRATION"):
    pytest.skip("voice integration off (set JARVIS_VOICE_INTEGRATION=1)", allow_module_level=True)

pytest.importorskip("piper")

from jarvis.config import config  # noqa: E402
from jarvis.voice.tts import PiperTTS  # noqa: E402


def test_speak_runs_without_raising():
    if not Path(config.tts_model_path).exists():
        pytest.skip(f"no piper voice at {config.tts_model_path}")

    PiperTTS().speak("hello from jarvis")  # synthesizes + plays locally; asserts no exception
