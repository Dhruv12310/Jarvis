"""__main__.main() dispatch: the 'selftest' subcommand vs the chat REPL. No Ollama."""

import jarvis.__main__ as entry


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
