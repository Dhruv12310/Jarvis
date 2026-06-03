"""Text-to-speech seam + the Piper implementation (the ONLY piper importer).

Piper is snappy and local; the voice runs on the Brain and audio never leaves the machine. The voice
model is a file the user downloads into ./data/piper/ (config.tts_model_path). Kokoro is a future
swap behind this same seam. The heavy import is lazy so this module loads without piper installed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from jarvis.config import config


class TextToSpeech(ABC):
    @abstractmethod
    def speak(self, text: str) -> None:
        """Synthesize ``text`` and play it locally."""


class PiperTTS(TextToSpeech):
    def __init__(self, model_path: Path | None = None) -> None:
        from piper import PiperVoice  # lazy: heavy import only when TTS is actually used

        self._voice = PiperVoice.load(str(model_path or config.tts_model_path))

    def speak(self, text: str) -> None:
        import numpy as np
        import sounddevice as sd

        chunks = list(self._voice.synthesize(text))
        if not chunks:
            return
        audio = np.concatenate([chunk.audio_int16_array for chunk in chunks])
        sd.play(audio, samplerate=chunks[0].sample_rate)
        sd.wait()
