"""Speech-to-text seam + the faster-whisper implementation (the ONLY faster_whisper importer).

The model auto-downloads from HuggingFace on first construction and runs locally thereafter; audio
never leaves the machine. The heavy import is lazy so this module loads (and the loop tests run)
without faster-whisper installed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from jarvis.config import config


class SpeechToText(ABC):
    @abstractmethod
    def transcribe(self, audio) -> str:
        """Transcribe 16 kHz mono float32 audio (or a file path) to text."""


class FasterWhisperSTT(SpeechToText):
    def __init__(
        self, model_size: str | None = None, device: str = "auto", compute_type: str = "default"
    ) -> None:
        from faster_whisper import WhisperModel  # lazy: heavy import only when STT is actually used

        self._model = WhisperModel(
            model_size or config.stt_model, device=device, compute_type=compute_type
        )

    def transcribe(self, audio) -> str:
        segments, _info = self._model.transcribe(audio, language="en")
        return " ".join(segment.text.strip() for segment in segments).strip()
