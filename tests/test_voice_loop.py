"""Voice loop wiring (no audio, no models): handle_turn transcribes -> asks -> speaks, via fakes.
Proves the transcript enters the same `service.ask` path and the answer is spoken when TTS is given.
"""

from jarvis.results import AskResult
from jarvis.voice.loop import handle_turn, run_voice_loop


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


def _one_then_eof(monkeypatch):
    # input() returns one Enter (start a turn) then raises EOFError to exit the loop.
    calls = iter([""])

    def fake_input(prompt=""):
        try:
            return next(calls)
        except StopIteration as stop:
            raise EOFError from stop

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr("jarvis.voice.audio.record_until_enter", lambda: object())


def test_run_voice_loop_prints_the_answer_then_exits(monkeypatch, capsys):
    _one_then_eof(monkeypatch)
    service = _FakeService(AskResult(text="the answer", grounded=True, cached=False))

    run_voice_loop(service, _FakeSTT("hello"))

    assert "jarvis> the answer" in capsys.readouterr().out


def test_run_voice_loop_reports_heard_nothing_on_empty(monkeypatch, capsys):
    _one_then_eof(monkeypatch)
    service = _FakeService(AskResult(text="x", grounded=True, cached=False))

    run_voice_loop(service, _FakeSTT("   "))  # empty transcript -> None

    assert "(heard nothing)" in capsys.readouterr().out
