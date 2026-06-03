"""CLI as a thin front-end over JarvisService (no network): command dispatch, ask rendering, and
REPL resilience. Builds a real service with faked/temp backends so nothing hits Ollama or the net.
Capability logic + signal taxonomy live in test_service.py; here we assert the CLI's rendering.
"""

import pytest

from jarvis.cli import _handle_command, _loop, _render_ask
from jarvis.knowledge.pipeline import Answer
from jarvis.memory.store import MemoryStore
from jarvis.orchestrator import Orchestrator
from jarvis.results import AskResult
from jarvis.service import JarvisService
from jarvis.signals.log import SignalLog
from jarvis.stores.chroma_store import ChromaVectorStore
from jarvis.stores.sqlite_store import SQLiteStructuredStore


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


def _cli(tmp_path, embedder, *, knowledge=None, llm=None):
    store = SQLiteStructuredStore(tmp_path / "jarvis.db")
    vector = ChromaVectorStore(tmp_path / "chroma", collection="memory", space="cosine")
    memory = MemoryStore(vector, embedder)
    service = JarvisService(
        orchestrator=Orchestrator(llm or _EchoLLM()),
        knowledge=knowledge or _FakeKnowledge(None),
        store=store,
        memory=memory,
        signals=SignalLog(store, session_id="s"),
        source="cli",
    )
    return service, store, memory


# --- command dispatch -------------------------------------------------------


def test_note_command_saves_and_confirms(tmp_path, capsys, fake_embedder):
    service, _store, memory = _cli(tmp_path, fake_embedder)

    _handle_command(":note buy milk", service)

    assert "saved to memory" in capsys.readouterr().out
    assert [r.content for r in memory.all()] == ["buy milk"]


def test_recall_finds_the_matching_memory(tmp_path, capsys, fake_embedder):
    service, _store, _memory = _cli(tmp_path, fake_embedder)
    _handle_command(":note schedule dentist appointment", service)
    _handle_command(":note buy groceries and milk", service)
    capsys.readouterr()

    _handle_command(":recall schedule dentist appointment", service)

    assert "schedule dentist appointment" in capsys.readouterr().out


def test_notes_command_lists_saved_memories(tmp_path, capsys, fake_embedder):
    service, _store, _memory = _cli(tmp_path, fake_embedder)
    _handle_command(":note alpha", service)
    _handle_command(":note beta", service)
    capsys.readouterr()

    _handle_command(":notes", service)

    out = capsys.readouterr().out
    assert "alpha" in out
    assert "beta" in out


def test_note_without_text_shows_usage_and_saves_nothing(tmp_path, capsys, fake_embedder):
    service, _store, memory = _cli(tmp_path, fake_embedder)

    _handle_command(":note", service)

    assert "usage: :note" in capsys.readouterr().out
    assert memory.all() == []


def test_recall_without_query_shows_usage(tmp_path, capsys, fake_embedder):
    service, _store, _memory = _cli(tmp_path, fake_embedder)

    _handle_command(":recall", service)

    assert "usage: :recall" in capsys.readouterr().out


def test_unknown_command_is_reported(tmp_path, capsys, fake_embedder):
    service, _store, _memory = _cli(tmp_path, fake_embedder)

    _handle_command(":bogus", service)

    assert "unknown command" in capsys.readouterr().out


def test_recall_with_no_matches_reports_empty(tmp_path, capsys, fake_embedder):
    service, _store, _memory = _cli(tmp_path, fake_embedder)

    _handle_command(":recall anything", service)

    assert "(no matches)" in capsys.readouterr().out


def test_notes_on_empty_store_reports_empty(tmp_path, capsys, fake_embedder):
    service, _store, _memory = _cli(tmp_path, fake_embedder)

    _handle_command(":notes", service)

    assert "(no memories yet)" in capsys.readouterr().out


def test_note_writes_nothing_when_embedding_fails(tmp_path):
    service, _store, memory = _cli(tmp_path, _FailingEmbedder())

    with pytest.raises(RuntimeError):
        _handle_command(":note hello", service)

    assert memory.all() == []  # save embeds before it upserts, so nothing half-commits


# --- goals ------------------------------------------------------------------


def test_goal_add_then_list_shows_it(tmp_path, capsys, fake_embedder):
    service, _store, _memory = _cli(tmp_path, fake_embedder)
    _handle_command(":goal add learn rust", service)
    capsys.readouterr()

    _handle_command(":goals", service)

    out = capsys.readouterr().out
    assert "learn rust" in out
    assert "[ ]" in out  # active


def test_goal_done_marks_it_complete(tmp_path, capsys, fake_embedder):
    service, store, _memory = _cli(tmp_path, fake_embedder)
    _handle_command(":goal add ship phase 3", service)
    goal_id = store.get_goals()[0].id
    capsys.readouterr()

    _handle_command(f":goal done {goal_id}", service)
    _handle_command(":goals", service)

    assert "[x]" in capsys.readouterr().out


def test_goal_add_without_text_shows_usage(tmp_path, capsys, fake_embedder):
    service, store, _memory = _cli(tmp_path, fake_embedder)

    _handle_command(":goal add", service)

    assert "usage: :goal add" in capsys.readouterr().out
    assert store.get_goals() == []


def test_goals_on_empty_store_reports_empty(tmp_path, capsys, fake_embedder):
    service, _store, _memory = _cli(tmp_path, fake_embedder)

    _handle_command(":goals", service)

    assert "(no goals yet)" in capsys.readouterr().out


# --- ask rendering (grounded -> cited, else labeled chat) --------------------


def test_render_ask_prints_grounded_result(capsys):
    _render_ask(AskResult(text="grounded summary", grounded=True, cached=False))

    out = capsys.readouterr().out
    assert "jarvis>" in out
    assert "grounded summary" in out


def test_render_ask_shows_cached_marker(capsys):
    _render_ask(AskResult(text="x", grounded=True, cached=True))

    assert "(cached)" in capsys.readouterr().out


def test_render_ask_labels_plain_chat(capsys):
    _render_ask(AskResult(text="chat reply", grounded=False, cached=False))

    out = capsys.readouterr().out
    assert "(chat)" in out
    assert "chat reply" in out


# --- REPL resilience --------------------------------------------------------


def test_loop_survives_a_backend_error_during_a_command(tmp_path, capsys, monkeypatch):
    service, _store, memory = _cli(tmp_path, _FailingEmbedder())
    lines = iter([":note hello", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(lines))

    _loop(service)

    out = capsys.readouterr().out
    assert "[error]" in out  # the failure surfaced and the loop kept going to "exit"
    assert memory.all() == []  # still no half-written memory


def test_loop_chat_turn_falls_back_and_prints_reply(tmp_path, capsys, fake_embedder, monkeypatch):
    service, _store, _memory = _cli(tmp_path, fake_embedder, knowledge=_FakeKnowledge(None))
    lines = iter(["hello there", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(lines))

    _loop(service)

    assert "jarvis (chat)> echo: hello there" in capsys.readouterr().out


def test_error_output_redacts_api_keys(tmp_path, capsys, fake_embedder, monkeypatch):
    class _LeakyKnowledge:
        def ask(self, question):
            raise RuntimeError("Client error for https://x?token=SECRET123&apikey=ABCDEF")

    service, _store, _memory = _cli(tmp_path, fake_embedder, knowledge=_LeakyKnowledge())
    lines = iter(["a question", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(lines))

    _loop(service)

    out = capsys.readouterr().out
    assert "SECRET123" not in out
    assert "ABCDEF" not in out
    assert "token=***" in out


def test_loop_brief_assembles_and_emits_signal(tmp_path, capsys, fake_embedder, monkeypatch):
    # No live calendar in the test: connect() returns None, so the briefing has no events.
    monkeypatch.setattr("jarvis.calendar.client.connect", lambda *a, **k: None)
    knowledge = _FakeKnowledge(Answer(text="markets up [1]", cached=False))
    service, store, _memory = _cli(tmp_path, fake_embedder, knowledge=knowledge)
    store.save_goal("ship phase 3")
    lines = iter([":brief", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(lines))

    _loop(service)

    out = capsys.readouterr().out
    assert "ship phase 3" in out  # active goal reached the data block the LLM phrased
    assert "markets up [1]" in out  # digest (with citation) reached the block
    assert any(e.kind == "briefing" for e in store.get_signals())


def test_loop_brief_survives_failing_sources(tmp_path, capsys, fake_embedder, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("calendar down")

    monkeypatch.setattr("jarvis.calendar.client.connect", boom)

    class _FailingKnowledge:
        def ask(self, question):
            raise RuntimeError("router down")

    service, store, _memory = _cli(tmp_path, fake_embedder, knowledge=_FailingKnowledge())
    store.save_goal("resilient goal")
    lines = iter([":brief", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(lines))

    _loop(service)

    out = capsys.readouterr().out
    assert "resilient goal" in out  # deterministic goals render despite both sources failing
    assert "[error]" not in out  # the briefing degraded gracefully, did not blow up


def test_loop_emits_a_signal_per_turn(tmp_path, fake_embedder, monkeypatch):
    service, store, _memory = _cli(tmp_path, fake_embedder)
    lines = iter([":notes", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(lines))

    _loop(service)

    assert any(e.kind == "memory_list" for e in store.get_signals())
