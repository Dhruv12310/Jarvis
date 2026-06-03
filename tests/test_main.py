"""__main__.main() dispatch: selftest / ui / voice subcommands vs the chat REPL. No Ollama/audio."""

from pathlib import Path

import jarvis.__main__ as entry


class _FakeStore:
    def __init__(self, events):
        self._events = events

    def close(self):
        self._events.append("close")


def test_main_runs_selftest_subcommand(monkeypatch):
    called = []

    def fake_selftest_main():
        called.append("selftest")
        return 0

    def fake_run():
        called.append("run")

    monkeypatch.setattr("jarvis.selftest.main", fake_selftest_main)
    monkeypatch.setattr("jarvis.cli.run", fake_run)
    monkeypatch.setattr("sys.argv", ["jarvis", "selftest"])

    assert entry.main() == 0
    assert called == ["selftest"]


def test_main_runs_chat_repl_by_default(monkeypatch):
    called = []

    def fake_run():
        called.append("run")

    def fake_selftest_main():
        called.append("selftest")
        return 0

    monkeypatch.setattr("jarvis.cli.run", fake_run)
    monkeypatch.setattr("jarvis.selftest.main", fake_selftest_main)
    monkeypatch.setattr("sys.argv", ["jarvis"])

    assert entry.main() == 0
    assert called == ["run"]


def test_main_propagates_selftest_exit_code(monkeypatch):
    monkeypatch.setattr("jarvis.selftest.main", lambda: 1)
    monkeypatch.setattr("sys.argv", ["jarvis", "selftest"])

    assert entry.main() == 1


def test_main_ui_subcommand_launches_then_closes(monkeypatch):
    events = []
    monkeypatch.setattr("jarvis.cli.build_service", lambda source: (object(), _FakeStore(events)))
    monkeypatch.setattr("jarvis.ui.app.launch", lambda service: events.append("launch"))
    monkeypatch.setattr("sys.argv", ["jarvis", "ui"])

    assert entry.main() == 0
    assert events == ["launch", "close"]  # launched, then the store was closed in finally


def test_main_voice_degrades_to_text_only_without_a_voice_file(monkeypatch, capsys):
    captured = {}

    class _Config:
        tts_model_path = Path("nonexistent-voice.onnx")

    monkeypatch.setattr("jarvis.config.config", _Config())
    monkeypatch.setattr("jarvis.cli.build_service", lambda source: (object(), _FakeStore([])))
    monkeypatch.setattr("jarvis.voice.stt.FasterWhisperSTT", lambda *a, **k: object())
    monkeypatch.setattr(
        "jarvis.voice.loop.run_voice_loop",
        lambda service, stt, tts=None: captured.update(tts=tts),
    )
    monkeypatch.setattr("sys.argv", ["jarvis", "voice"])

    assert entry.main() == 0
    assert captured["tts"] is None  # no voice file -> ran voice-to-text only
    assert "voice-to-text only" in capsys.readouterr().out
