"""Microphone capture for push-to-talk (the ONLY sounddevice importer for input).

Records until the user presses Enter and returns a 16 kHz mono float32 array - the format
faster-whisper expects. sounddevice is imported lazily so the loop wiring tests don't need an
audio device.
"""

from __future__ import annotations

SAMPLE_RATE = 16000  # faster-whisper expects 16 kHz mono


def record_until_enter():
    """Capture mic audio until Enter is pressed; return a 16 kHz mono float32 numpy array."""
    import numpy as np
    import sounddevice as sd

    frames: list = []

    def _callback(indata, _frames, _time, _status):
        frames.append(indata.copy())

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=_callback):
        input()  # block until Enter -> stop recording

    if not frames:
        return np.zeros(0, dtype="float32")
    return np.concatenate(frames, axis=0).reshape(-1)
