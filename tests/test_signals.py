"""Signal capture: every interaction appends a SignalEvent; capture never breaks an interaction."""

from datetime import datetime

from jarvis.signals.log import SignalLog
from jarvis.stores.sqlite_store import SQLiteStructuredStore


def _store(tmp_path):
    return SQLiteStructuredStore(tmp_path / "jarvis.db")


def test_emit_appends_a_signal_event(tmp_path):
    store = _store(tmp_path)

    SignalLog(store, session_id="s1").emit("query", {"path": "hn"})

    signals = store.get_signals()
    assert len(signals) == 1
    event = signals[0]
    assert event.kind == "query"
    assert event.payload == {"path": "hn"}
    assert event.session_id == "s1"
    assert isinstance(event.ts, datetime)
    assert event.id  # a uuid string


def test_get_signals_newest_first(tmp_path):
    log = SignalLog(_store(tmp_path), session_id="s1")
    log.emit("a")
    log.emit("b")

    assert [e.kind for e in log._store.get_signals()] == ["b", "a"]


def test_emit_swallows_store_failure():
    class _BoomStore:
        def save_signal(self, event):
            raise RuntimeError("store down")

    SignalLog(_BoomStore(), session_id="s1").emit("query", {})  # must NOT raise


def test_signals_persist_across_instances(tmp_path):
    path = tmp_path / "jarvis.db"
    first = SQLiteStructuredStore(path)
    SignalLog(first, session_id="s1").emit("x", {"k": 1})
    first.close()

    events = SQLiteStructuredStore(path).get_signals()
    assert [e.kind for e in events] == ["x"]
    assert events[0].payload == {"k": 1}


def test_one_session_id_across_emits(tmp_path):
    log = SignalLog(_store(tmp_path))  # generated session id
    log.emit("a")
    log.emit("b")

    assert len({e.session_id for e in log._store.get_signals()}) == 1
