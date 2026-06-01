"""CLI command dispatch (no network): :note saves, :notes lists, errors are reported.

Exercises the command handler against a real temp-backed store, proving the structured-store half
of the Phase 0 DoD end to end without Ollama.
"""

from jarvis.cli import _handle_command
from jarvis.stores.sqlite_store import SQLiteStructuredStore


def _store(tmp_path):
    return SQLiteStructuredStore(tmp_path / "jarvis.db")


def test_note_command_saves_and_reports_id(tmp_path, capsys):
    store = _store(tmp_path)

    _handle_command(":note buy milk", store)

    assert "saved note #1" in capsys.readouterr().out
    assert [n.content for n in store.get_notes()] == ["buy milk"]


def test_notes_command_lists_saved_notes(tmp_path, capsys):
    store = _store(tmp_path)
    store.save_note("alpha")
    store.save_note("beta")

    _handle_command(":notes", store)

    out = capsys.readouterr().out
    assert "alpha" in out
    assert "beta" in out


def test_note_without_text_shows_usage_and_saves_nothing(tmp_path, capsys):
    store = _store(tmp_path)

    _handle_command(":note", store)

    assert "usage: :note" in capsys.readouterr().out
    assert store.get_notes() == []


def test_unknown_command_is_reported(tmp_path, capsys):
    store = _store(tmp_path)

    _handle_command(":bogus", store)

    assert "unknown command" in capsys.readouterr().out
