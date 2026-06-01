"""CLI dispatch (no network): :note/:notes/:recall commands, the knowledge/chat answer path,
and the REPL's resilience. Uses fakes/temp stores so nothing hits Ollama or the network.
"""

import pytest

from jarvis.cli import _answer, _handle_command, _loop
from jarvis.knowledge.pipeline import Answer
from jarvis.orchestrator import Orchestrator
from jarvis.stores.chroma_store import ChromaVectorStore
from jarvis.stores.sqlite_store import SQLiteStructuredStore


def _backends(tmp_path):
    store = SQLiteStructuredStore(tmp_path / "jarvis.db")
    vector = ChromaVectorStore(tmp_path / "chroma")
    return store, vector


class _FailingEmbedder:
    def embed(self, text: str) -> list[float]:
        raise RuntimeError("embedder down")


class _EchoLLM:
    def generate(self, prompt: str) -> str:
        return f"echo: {prompt}"


class _FakeKnowledge:
    """Stands in for the knowledge pipeline: ``ask`` returns a preset Answer or None."""

    def __init__(self, result=None):
        self._result = result

    def ask(self, question):
        return self._result


# --- command dispatch -------------------------------------------------------


def test_note_command_saves_embeds_and_reports_id(tmp_path, capsys, fake_embedder):
    store, vector = _backends(tmp_path)

    _handle_command(":note buy milk", store, vector, fake_embedder)

    assert "saved note #1" in capsys.readouterr().out
    assert [n.content for n in store.get_notes()] == ["buy milk"]


def test_recall_finds_the_matching_note(tmp_path, capsys, fake_embedder):
    store, vector = _backends(tmp_path)
    _handle_command(":note schedule dentist appointment", store, vector, fake_embedder)
    _handle_command(":note buy groceries and milk", store, vector, fake_embedder)
    capsys.readouterr()

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


def test_recall_with_no_matches_reports_empty(tmp_path, capsys, fake_embedder):
    store, vector = _backends(tmp_path)

    _handle_command(":recall anything", store, vector, fake_embedder)

    assert "(no matches)" in capsys.readouterr().out


def test_notes_on_empty_store_reports_empty(tmp_path, capsys, fake_embedder):
    store, vector = _backends(tmp_path)

    _handle_command(":notes", store, vector, fake_embedder)

    assert "(no notes yet)" in capsys.readouterr().out


def test_note_writes_nothing_when_embedding_fails(tmp_path):
    store, vector = _backends(tmp_path)

    with pytest.raises(RuntimeError):
        _handle_command(":note hello", store, vector, _FailingEmbedder())

    assert store.get_notes() == []


# --- answer path (knowledge -> grounded, else labeled chat) -----------------


def test_answer_prints_grounded_result(capsys):
    knowledge = _FakeKnowledge(Answer(text="grounded summary", cached=False))

    _answer("q", knowledge, orchestrator=None)

    out = capsys.readouterr().out
    assert "jarvis>" in out
    assert "grounded summary" in out


def test_answer_shows_cached_marker(capsys):
    knowledge = _FakeKnowledge(Answer(text="x", cached=True))

    _answer("q", knowledge, orchestrator=None)

    assert "(cached)" in capsys.readouterr().out


def test_answer_falls_back_to_labeled_chat_when_no_connector(capsys):
    class _Chat:
        def chat(self, text):
            return "chat reply"

    _answer("q", _FakeKnowledge(None), _Chat())

    out = capsys.readouterr().out
    assert "(chat)" in out
    assert "chat reply" in out


# --- REPL resilience --------------------------------------------------------


def test_loop_survives_a_backend_error_during_a_command(tmp_path, capsys, monkeypatch):
    store, vector = _backends(tmp_path)
    lines = iter([":note hello", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(lines))

    _loop(
        orchestrator=None,
        knowledge=_FakeKnowledge(),
        store=store,
        vector=vector,
        embedder=_FailingEmbedder(),
    )

    out = capsys.readouterr().out
    assert "[error]" in out  # the failure surfaced and the loop kept going to "exit"
    assert store.get_notes() == []  # still no half-written note


def test_loop_chat_turn_falls_back_and_prints_reply(tmp_path, capsys, fake_embedder, monkeypatch):
    store, vector = _backends(tmp_path)
    orchestrator = Orchestrator(_EchoLLM())
    lines = iter(["hello there", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(lines))

    _loop(orchestrator, _FakeKnowledge(None), store, vector, fake_embedder)

    assert "jarvis (chat)> echo: hello there" in capsys.readouterr().out
