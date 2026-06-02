"""CLI dispatch (no network): :note/:notes/:recall commands, the knowledge/chat answer path,
and the REPL's resilience. Uses fakes/temp stores so nothing hits Ollama or the network.
"""

import pytest

from jarvis.cli import _answer, _handle_command, _loop
from jarvis.knowledge.pipeline import Answer
from jarvis.memory.store import MemoryStore
from jarvis.orchestrator import Orchestrator
from jarvis.signals.log import SignalLog
from jarvis.stores.chroma_store import ChromaVectorStore
from jarvis.stores.sqlite_store import SQLiteStructuredStore


def _backends(tmp_path, embedder):
    store = SQLiteStructuredStore(tmp_path / "jarvis.db")
    vector = ChromaVectorStore(tmp_path / "chroma", collection="memory", space="cosine")
    return store, MemoryStore(vector, embedder)


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


def test_note_command_saves_and_confirms(tmp_path, capsys, fake_embedder):
    store, memory = _backends(tmp_path, fake_embedder)

    _handle_command(":note buy milk", store, memory)

    assert "saved to memory" in capsys.readouterr().out
    assert [r.content for r in memory.all()] == ["buy milk"]


def test_recall_finds_the_matching_memory(tmp_path, capsys, fake_embedder):
    store, memory = _backends(tmp_path, fake_embedder)
    _handle_command(":note schedule dentist appointment", store, memory)
    _handle_command(":note buy groceries and milk", store, memory)
    capsys.readouterr()

    _handle_command(":recall schedule dentist appointment", store, memory)

    assert "schedule dentist appointment" in capsys.readouterr().out


def test_notes_command_lists_saved_memories(tmp_path, capsys, fake_embedder):
    store, memory = _backends(tmp_path, fake_embedder)
    _handle_command(":note alpha", store, memory)
    _handle_command(":note beta", store, memory)
    capsys.readouterr()

    _handle_command(":notes", store, memory)

    out = capsys.readouterr().out
    assert "alpha" in out
    assert "beta" in out


def test_note_without_text_shows_usage_and_saves_nothing(tmp_path, capsys, fake_embedder):
    store, memory = _backends(tmp_path, fake_embedder)

    _handle_command(":note", store, memory)

    assert "usage: :note" in capsys.readouterr().out
    assert memory.all() == []


def test_recall_without_query_shows_usage(tmp_path, capsys, fake_embedder):
    store, memory = _backends(tmp_path, fake_embedder)

    _handle_command(":recall", store, memory)

    assert "usage: :recall" in capsys.readouterr().out


def test_unknown_command_is_reported(tmp_path, capsys, fake_embedder):
    store, memory = _backends(tmp_path, fake_embedder)

    _handle_command(":bogus", store, memory)

    assert "unknown command" in capsys.readouterr().out


def test_recall_with_no_matches_reports_empty(tmp_path, capsys, fake_embedder):
    store, memory = _backends(tmp_path, fake_embedder)

    _handle_command(":recall anything", store, memory)

    assert "(no matches)" in capsys.readouterr().out


def test_notes_on_empty_store_reports_empty(tmp_path, capsys, fake_embedder):
    store, memory = _backends(tmp_path, fake_embedder)

    _handle_command(":notes", store, memory)

    assert "(no memories yet)" in capsys.readouterr().out


def test_note_writes_nothing_when_embedding_fails(tmp_path):
    store, memory = _backends(tmp_path, _FailingEmbedder())

    with pytest.raises(RuntimeError):
        _handle_command(":note hello", store, memory)

    assert memory.all() == []  # save embeds before it upserts, so nothing half-commits


# --- goals ------------------------------------------------------------------


def test_goal_add_then_list_shows_it(tmp_path, capsys, fake_embedder):
    store, memory = _backends(tmp_path, fake_embedder)
    _handle_command(":goal add learn rust", store, memory)
    capsys.readouterr()

    _handle_command(":goals", store, memory)

    out = capsys.readouterr().out
    assert "learn rust" in out
    assert "[ ]" in out  # active


def test_goal_done_marks_it_complete(tmp_path, capsys, fake_embedder):
    store, memory = _backends(tmp_path, fake_embedder)
    _handle_command(":goal add ship phase 2", store, memory)
    goal_id = store.get_goals()[0].id
    capsys.readouterr()

    _handle_command(f":goal done {goal_id}", store, memory)
    _handle_command(":goals", store, memory)

    assert "[x]" in capsys.readouterr().out


def test_goal_add_without_text_shows_usage(tmp_path, capsys, fake_embedder):
    store, memory = _backends(tmp_path, fake_embedder)

    _handle_command(":goal add", store, memory)

    assert "usage: :goal add" in capsys.readouterr().out
    assert store.get_goals() == []


def test_goals_on_empty_store_reports_empty(tmp_path, capsys, fake_embedder):
    store, memory = _backends(tmp_path, fake_embedder)

    _handle_command(":goals", store, memory)

    assert "(no goals yet)" in capsys.readouterr().out


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
    store, memory = _backends(tmp_path, _FailingEmbedder())
    lines = iter([":note hello", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(lines))

    _loop(
        orchestrator=None,
        knowledge=_FakeKnowledge(),
        store=store,
        memory=memory,
        signals=SignalLog(store),
    )

    out = capsys.readouterr().out
    assert "[error]" in out  # the failure surfaced and the loop kept going to "exit"
    assert memory.all() == []  # still no half-written memory


def test_loop_chat_turn_falls_back_and_prints_reply(tmp_path, capsys, fake_embedder, monkeypatch):
    store, memory = _backends(tmp_path, fake_embedder)
    orchestrator = Orchestrator(_EchoLLM())
    lines = iter(["hello there", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(lines))

    _loop(orchestrator, _FakeKnowledge(None), store, memory, SignalLog(store))

    assert "jarvis (chat)> echo: hello there" in capsys.readouterr().out


def test_error_output_redacts_api_keys(tmp_path, capsys, fake_embedder, monkeypatch):
    store, memory = _backends(tmp_path, fake_embedder)

    class _LeakyKnowledge:
        def ask(self, question):
            raise RuntimeError("Client error for https://x?token=SECRET123&apikey=ABCDEF")

    lines = iter(["a question", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(lines))

    _loop(None, _LeakyKnowledge(), store, memory, SignalLog(store))

    out = capsys.readouterr().out
    assert "SECRET123" not in out
    assert "ABCDEF" not in out
    assert "token=***" in out


def test_loop_emits_a_signal_per_turn(tmp_path, fake_embedder, monkeypatch):
    store, memory = _backends(tmp_path, fake_embedder)
    signals = SignalLog(store, session_id="s")
    lines = iter([":notes", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(lines))

    _loop(Orchestrator(_EchoLLM()), _FakeKnowledge(None), store, memory, signals)

    events = store.get_signals()
    assert any(e.kind == "command" and e.payload.get("command") == "notes" for e in events)
