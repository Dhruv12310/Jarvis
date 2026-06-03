"""Live STT (gated integration): faster-whisper transcribes audio without raising.

Like the keyed-connector and OAuth integration tests, this is OFF by default - set
JARVIS_VOICE_INTEGRATION=1 (with the model downloadable) to run it on the Brain.
"""

import os

import pytest

pytestmark = pytest.mark.integration

if not os.environ.get("JARVIS_VOICE_INTEGRATION"):
    pytest.skip("voice integration off (set JARVIS_VOICE_INTEGRATION=1)", allow_module_level=True)

pytest.importorskip("faster_whisper")

import numpy as np  # noqa: E402

from jarvis.voice.stt import FasterWhisperSTT  # noqa: E402


def test_transcribe_returns_a_string():
    stt = FasterWhisperSTT(model_size="tiny")  # small model for a fast gated run

    result = stt.transcribe(np.zeros(16000, dtype="float32"))  # 1s silence

    assert isinstance(result, str)
