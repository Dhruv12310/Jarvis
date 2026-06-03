"""JarvisService facade: each capability returns the right result AND emits exactly one SignalEvent
stamped with `source`. Core is faked/temp so nothing hits Ollama, the network, or the real calendar.
"""

import pytest

from jarvis.knowledge.pipeline import Answer
from jarvis.memory.store import MemoryStore
from jarvis.orchestrator import Orchestrator
from jarvis.results import AgendaResult, AskResult
from jarvis.service import JarvisService
from jarvis.signals.log import SignalLog
from jarvis.stores.sqlite_store import SQLiteStructuredStore
from tests.test_memory_store import _FakeVector


class _EchoLLM:
    def generate(self, prompt: str, **_kwargs) -> str:
        return f"echo: {prompt}"


class _FakeKnowledge:
    def __init__(self, result=None):
        self._result = result

    def ask(self, question):
        return self._result


def _service(tmp_path, fake_embedder, *, knowledge=None, llm=None, source="cli"):
    store = SQLiteStructuredStore(tmp_path / "jarvis.db")
    memory = MemoryStore(_FakeVector(), fake_embedder)
    signals = SignalLog(store, session_id="s")
    service = JarvisService(
        orchestrator=Orchestrator(llm or _EchoLLM()),
        knowledge=knowledge or _FakeKnowledge(None),
        store=store,
        memory=memory,
        signals=signals,
        source=source,
    )
    return service, store


def test_ask_grounded_returns_result_and_one_signal(tmp_path, fake_embedder):
    service, store = _service(
        tmp_path, fake_embedder, knowledge=_FakeKnowledge(Answer("g", cached=True))
    )

    result = service.ask("q")

    assert result == AskResult(text="g", grounded=True, cached=True)
    [sig] = store.get_signals()
    assert sig.kind == "ask"
    assert sig.payload == {"source": "cli", "path": "knowledge", "cached": True}


def test_ask_falls_back_to_chat(tmp_path, fake_embedder):
    service, store = _service(tmp_path, fake_embedder, knowledge=_FakeKnowledge(None))

    result = service.ask("hello")

    assert result.grounded is False
    assert result.text == "echo: hello"
    assert store.get_signals()[0].payload["path"] == "chat"


def test_goals_crud_each_emit_a_signal(tmp_path, fake_embedder):
    service, store = _service(tmp_path, fake_embedder)

    goal = service.add_goal("ship phase 3")
    assert [g.description for g in service.list_goals()] == ["ship phase 3"]
    done = service.complete_goal(goal.id)

    assert done.status == "done"
    kinds = [s.kind for s in store.get_signals()]
    assert kinds.count("goal_add") == 1
    assert kinds.count("goal_list") == 1
    assert kinds.count("goal_done") == 1


def test_memory_remember_recall_and_list(tmp_path, fake_embedder):
    service, store = _service(tmp_path, fake_embedder)

    service.remember("dentist friday")
    assert [r.content for r in service.memories()] == ["dentist friday"]
    assert service.recall("dentist friday")[0].content == "dentist friday"
    assert {s.kind for s in store.get_signals()} >= {"remember", "memory_list", "recall"}


def test_agenda_reports_not_connected(tmp_path, fake_embedder, monkeypatch):
    monkeypatch.setattr("jarvis.calendar.client.connect", lambda *a, **k: None)
    service, store = _service(tmp_path, fake_embedder)

    result = service.agenda()

    assert result == AgendaResult(events=[], connected=False)
    assert store.get_signals()[0].payload == {"source": "cli", "connected": False, "count": 0}


def test_agenda_connected_lists_events_and_stamps_count(tmp_path, fake_embedder, monkeypatch):
    events = [object(), object()]

    class _Client:
        def list_events(self, *_a, **_k):
            return events

    monkeypatch.setattr("jarvis.calendar.client.connect", lambda *a, **k: _Client())
    service, store = _service(tmp_path, fake_embedder)

    result = service.agenda()

    assert result == AgendaResult(events=events, connected=True)
    assert store.get_signals()[0].payload == {"source": "cli", "connected": True, "count": 2}


def test_agenda_degrades_when_calendar_raises(tmp_path, fake_embedder, monkeypatch):
    def _boom(*_a, **_k):
        raise RuntimeError("calendar down")

    monkeypatch.setattr("jarvis.calendar.client.connect", _boom)
    service, store = _service(tmp_path, fake_embedder)

    result = service.agenda()  # must NOT raise - degrades like the briefing does

    assert result == AgendaResult(events=[], connected=False)


def test_briefing_phrases_and_emits(tmp_path, fake_embedder, monkeypatch):
    monkeypatch.setattr("jarvis.calendar.client.connect", lambda *a, **k: None)
    service, store = _service(tmp_path, fake_embedder)
    service.add_goal("resilient goal")

    text = service.briefing()

    assert "resilient goal" in text  # active goal reached the block the LLM phrased
    assert any(s.kind == "briefing" for s in store.get_signals())


def test_every_call_stamps_source(tmp_path, fake_embedder):
    service, store = _service(tmp_path, fake_embedder, source="gui")

    service.add_goal("x")

    assert store.get_signals()[0].payload["source"] == "gui"


def test_failure_still_emits_a_signal_with_error_then_reraises(tmp_path, fake_embedder):
    service, store = _service(tmp_path, fake_embedder)

    with pytest.raises(LookupError):
        service.complete_goal(999)  # no such goal

    [sig] = store.get_signals()
    assert sig.kind == "goal_done"
    assert sig.payload["error"] == "LookupError"
    assert sig.payload["source"] == "cli"


def test_recent_signals_is_a_non_emitting_inspector(tmp_path, fake_embedder):
    service, store = _service(tmp_path, fake_embedder)
    service.add_goal("x")  # 1 signal

    rows = service.recent_signals(limit=10)

    assert len(rows) == 1  # the inspector itself did not add a signal
