"""CLI command dispatch (no network): :note saves and embeds, :notes lists, :recall finds.

Uses a deterministic fake embedder and temp-backed stores, proving the full note path
(save -> embed -> recall) end to end without Ollama.
"""

from jarvis.cli import _handle_command
from jarvis.stores.chroma_store import ChromaVectorStore
from jarvis.stores.sqlite_store import SQLiteStructuredStore


def _backends(tmp_path):
    store = SQLiteStructuredStore(tmp_path / "jarvis.db")
    vector = ChromaVectorStore(tmp_path / "chroma")
    return store, vector


def test_note_command_saves_embeds_and_reports_id(tmp_path, capsys, fake_embedder):
    store, vector = _backends(tmp_path)

    _handle_command(":note buy milk", store, vector, fake_embedder)

    assert "saved note #1" in capsys.readouterr().out
    assert [n.content for n in store.get_notes()] == ["buy milk"]


def test_recall_finds_the_matching_note(tmp_path, capsys, fake_embedder):
    store, vector = _backends(tmp_path)
    _handle_command(":note schedule dentist appointment", store, vector, fake_embedder)
    _handle_command(":note buy groceries and milk", store, vector, fake_embedder)
    capsys.readouterr()  # discard the save output

    _handle_command(":recall schedule dentist appointment", store, vector, fake_embedder)

    assert "schedule dentist appointment" in capsys.readouterr().out


def test_notes_command_lists_saved_notes(tmp_path, capsys, fake_embedder):
    store, vector = _backends(tmp_path)
    _handle_command(":note alpha", store, vector, fake_embedder)
    _handle_command(":note beta", store, vector, fake_embedder)
    capsys.readouterr()

    _handle_command(":notes", store, vector, fake_embedder)

    out = capsys.readouterr().out
    assert "alpha" in out
    assert "beta" in out


def test_note_without_text_shows_usage_and_saves_nothing(tmp_path, capsys, fake_embedder):
    store, vector = _backends(tmp_path)

    _handle_command(":note", store, vector, fake_embedder)

    assert "usage: :note" in capsys.readouterr().out
    assert store.get_notes() == []


def test_recall_without_query_shows_usage(tmp_path, capsys, fake_embedder):
    store, vector = _backends(tmp_path)

    _handle_command(":recall", store, vector, fake_embedder)

    assert "usage: :recall" in capsys.readouterr().out


def test_unknown_command_is_reported(tmp_path, capsys, fake_embedder):
    store, vector = _backends(tmp_path)

    _handle_command(":bogus", store, vector, fake_embedder)

    assert "unknown command" in capsys.readouterr().out
