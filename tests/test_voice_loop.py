"""Voice loop wiring (no audio, no models): handle_turn transcribes -> asks -> speaks, via fakes.
Proves the transcript enters the same `service.ask` path and the answer is spoken when TTS is given.
"""

from jarvis.results import AskResult
from jarvis.voice.loop import handle_turn


class _FakeSTT:
    def __init__(self, text):
        self._text = text

    def transcribe(self, audio):
        return self._text


class _FakeService:
    def __init__(self, answer):
        self._answer = answer
        self.asked: list[str] = []

    def ask(self, text):
        self.asked.append(text)
        return self._answer


class _FakeTTS:
    def __init__(self):
        self.spoken: list[str] = []

    def speak(self, text):
        self.spoken.append(text)


def test_handle_turn_transcribes_then_asks():
    service = _FakeService(AskResult(text="the answer", grounded=True, cached=False))

    answer = handle_turn(service, _FakeSTT("what is up"), audio=object())

    assert service.asked == ["what is up"]  # transcript entered the same pipeline
    assert answer == "the answer"


def test_handle_turn_speaks_the_answer_when_tts_given():
    service = _FakeService(AskResult(text="spoken answer", grounded=True, cached=False))
    tts = _FakeTTS()

    handle_turn(service, _FakeSTT("hi"), audio=object(), tts=tts)

    assert tts.spoken == ["spoken answer"]


def test_handle_turn_ignores_an_empty_transcript():
    service = _FakeService(AskResult(text="x", grounded=True, cached=False))
    tts = _FakeTTS()

    answer = handle_turn(service, _FakeSTT("   "), audio=object(), tts=tts)

    assert answer is None
    assert service.asked == []  # nothing heard -> the pipeline is not called
    assert tts.spoken == []
