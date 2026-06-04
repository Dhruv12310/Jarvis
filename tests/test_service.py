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
        llm=llm,  # facade's structured-parse LLM (finance); None for non-finance tests
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


def test_recategorize_persists_and_signals_without_a_merchant_string(tmp_path, fake_embedder):
    from datetime import date
    from decimal import Decimal

    from jarvis.finance.transaction import Transaction, make_id

    service, store = _service(tmp_path, fake_embedder)
    day, amt = date(2026, 1, 5), Decimal("-9.99")
    store.save_transactions(
        [Transaction(make_id("chk", day, amt, "SHELL"), day, amt, "SHELL", "transport", "chk")]
    )

    count = service.recategorize("SHELL", "groceries")

    assert count == 1
    assert store.get_transactions()[0].category == "groceries"
    [sig] = store.get_signals()
    assert sig.kind == "recategorize"
    assert sig.payload == {"source": "cli", "category": "groceries", "updated": 1}
    assert "SHELL" not in str(sig.payload)  # trust boundary: no merchant string in the log


def _finance_txn(merchant, category, *, day=None, amount="-9.99", account="chk"):
    from datetime import date
    from decimal import Decimal

    from jarvis.finance.transaction import Transaction, make_id

    day = day or date(2026, 1, 5)
    amt = Decimal(amount)
    return Transaction(make_id(account, day, amt, merchant), day, amt, merchant, category, account)


def test_categorize_unknowns_fills_via_the_llm(tmp_path, fake_embedder):
    import json

    class _CatLLM:
        def generate(self, prompt, *, format=None, think=None):
            return json.dumps({"category": "entertainment"})

    service, store = _service(tmp_path, fake_embedder, llm=_CatLLM())
    store.save_transactions([_finance_txn("OBSCURE VENUE", "uncategorized")])

    count = service.categorize_unknowns()

    assert count == 1
    assert store.get_transactions()[0].category == "entertainment"
    assert any(s.kind == "categorize" for s in store.get_signals())


def test_brief_finance_reports_month_total_and_top_category(tmp_path, fake_embedder, monkeypatch):
    from datetime import date

    service, store = _service(tmp_path, fake_embedder)
    today = date.today()
    store.save_transactions(
        [
            _finance_txn("CHIPOTLE", "dining", day=today, amount="-30.00"),
            _finance_txn("UBER", "transport", day=today, amount="-15.00", account="cc"),
        ]
    )

    line = service._brief_finance()

    assert line is not None
    assert "$45.00" in line  # engine total
    assert "dining" in line and "$30.00" in line  # top category


def test_brief_finance_is_none_without_month_data(tmp_path, fake_embedder):
    service, _store = _service(tmp_path, fake_embedder)

    assert service._brief_finance() is None


def test_set_budget_rejects_an_unknown_category(tmp_path, fake_embedder):
    from decimal import Decimal

    service, _store = _service(tmp_path, fake_embedder)

    with pytest.raises(ValueError):
        service.set_budget("not-a-category", Decimal("100"))


def test_reflect_skips_below_threshold_and_signals_metadata_only(tmp_path, fake_embedder):
    service, store = _service(tmp_path, fake_embedder)  # empty signal log -> no fuel

    written = service.reflect(force=False)

    assert written == 0
    [sig] = store.get_signals()
    assert sig.kind == "reflect" and sig.payload == {"source": "cli", "reflected": False}


def test_reflect_forced_runs_synthesis_and_writes_inferred_memory(tmp_path, fake_embedder):
    import json

    class _ReflLLM:
        def generate(self, prompt, *, format=None, think=None):
            # a behavioral insight grounded on the "signals" aggregate (no memory needed)
            return json.dumps(
                {
                    "insights": [
                        {"kind": "rhythm", "content": "works in the morning", "links": ["signals"]}
                    ]
                }
            )

    service, store = _service(tmp_path, fake_embedder, llm=_ReflLLM())

    written = service.reflect(force=True)

    assert written == 1
    assert any(m.type == "reflection" for m in service.memories())  # the inferred memory was saved
    refl = [s for s in store.get_signals() if s.kind == "reflect"][0]
    assert refl.payload["insights"] == 1 and refl.payload["forced"] is True
    assert "morning" not in str(refl.payload)  # no insight content in the signal log


def test_reflect_advances_baseline_to_processed_window_not_global_max(tmp_path, fake_embedder):
    import json

    class _ReflLLM:
        def generate(self, prompt, *, format=None, think=None):
            return json.dumps(
                {"insights": [{"kind": "rhythm", "content": "mornings", "links": ["signals"]}]}
            )

    service, store = _service(tmp_path, fake_embedder, llm=_ReflLLM())
    service.add_goal("learn rust")  # a real signal inside the window

    service.reflect(force=True)

    # The reflect signal is appended AFTER the processed window; the baseline must sit at the window
    # max, strictly below the global max - else a write during synthesis would be skipped forever.
    assert store.get_reflection_state().last_seq < store.latest_signal_seq()


def test_reflect_hard_failure_leaves_baseline_unadvanced(tmp_path, fake_embedder):
    class _BadLLM:
        def generate(self, prompt, *, format=None, think=None):
            raise RuntimeError("ollama down")

    service, store = _service(tmp_path, fake_embedder, llm=_BadLLM())
    service.add_goal("learn rust")  # fuel in the window

    written = service.reflect(force=True)

    assert written == 0
    assert store.get_reflection_state().last_seq == 0  # window NOT consumed -> retried next run
    refl = [s for s in store.get_signals() if s.kind == "reflect"][0]
    assert refl.payload["reflected"] is False and refl.payload["error"] == "RuntimeError"


def test_suppress_topic_pulls_down_a_weight_without_leaking_the_topic(tmp_path, fake_embedder):
    service, store = _service(tmp_path, fake_embedder)
    store.save_user_model(
        {
            "interests": [
                {
                    "topic": "rust",
                    "weight": 0.6,
                    "confidence": 0.6,
                    "last_updated": "2026-06-03T09:00:00",
                }
            ],
            "rhythms": [],
            "preferences": [],
            "updated_at": None,
        }
    )

    service.suppress_topic("rust")

    rust = next(i for i in service.user_model().interests if i.topic == "rust")
    assert rust.weight < 0.6 and rust.confidence < 0.6  # the user pulled it down
    sig = [s for s in store.get_signals() if s.kind == "suppress_topic"][0]
    assert "rust" not in str(sig.payload)  # free-text topic stays out of the signal log


def test_user_model_is_inspectable_with_live_goals(tmp_path, fake_embedder):
    service, _store = _service(tmp_path, fake_embedder)
    service.add_goal("learn rust")

    model = service.user_model()

    assert [g.description for g in model.goals] == ["learn rust"]  # goals read live


def test_reset_user_model_clears_the_derived_profile(tmp_path, fake_embedder):
    service, store = _service(tmp_path, fake_embedder)
    store.save_user_model(
        {
            "interests": [
                {
                    "topic": "x",
                    "weight": 0.3,
                    "confidence": 0.3,
                    "last_updated": "2026-06-03T09:00:00",
                }
            ],
            "rhythms": [],
            "preferences": [],
            "updated_at": None,
        }
    )
    assert service.user_model().interests  # present

    service.reset_user_model()

    assert service.user_model().interests == []


def test_forget_deletes_a_memory(tmp_path, fake_embedder):
    service, _store = _service(tmp_path, fake_embedder)
    record = service.remember("a private thing")
    assert service.memories()

    service.forget(record.id)

    assert service.memories() == []


def test_add_watch_uppercases_symbols_and_logs_metadata_only(tmp_path, fake_embedder):
    service, store = _service(tmp_path, fake_embedder)

    service.add_watch("symbol", "nvda")
    service.add_watch("topic", "local LLMs")

    assert {(w.kind, w.value) for w in service.watchlist()} == {
        ("symbol", "NVDA"),
        ("topic", "local LLMs"),
    }
    sig = [s for s in store.get_signals() if s.kind == "watch_add"][0]
    assert "NVDA" not in str(sig.payload)  # the term stays out of the signal log


def test_recent_signals_is_a_non_emitting_inspector(tmp_path, fake_embedder):
    service, store = _service(tmp_path, fake_embedder)
    service.add_goal("x")  # 1 signal

    rows = service.recent_signals(limit=10)

    assert len(rows) == 1  # the inspector itself did not add a signal
