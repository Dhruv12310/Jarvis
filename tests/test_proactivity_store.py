"""Proactivity store: the signal-window query (get_signals_since / latest_signal_seq) and the
reflection-state baseline round-trip (temp SQLite)."""

from datetime import UTC, datetime

from jarvis.signals.log import SignalLog
from jarvis.stores.sqlite_store import SQLiteStructuredStore
from jarvis.stores.structured import ReflectionState


def _emit(store, kind):
    SignalLog(store, session_id="s").emit(kind)


def test_get_signals_since_returns_the_window_oldest_first(tmp_path):
    store = SQLiteStructuredStore(tmp_path / "j.db")
    _emit(store, "ask")  # seq 1
    _emit(store, "goal_done")  # seq 2
    _emit(store, "recall")  # seq 3

    since = store.get_signals_since(1)

    assert [s.kind for s in since] == ["goal_done", "recall"]  # seq > 1, oldest first
    assert store.latest_signal_seq() == 3


def test_latest_seq_is_zero_on_an_empty_log(tmp_path):
    store = SQLiteStructuredStore(tmp_path / "j.db")

    assert store.latest_signal_seq() == 0
    assert store.get_signals_since(0) == []


def test_reflection_state_round_trip(tmp_path):
    store = SQLiteStructuredStore(tmp_path / "j.db")

    assert store.get_reflection_state() == ReflectionState(last_seq=0, last_reflection_at=None)

    now = datetime.now(UTC)
    store.save_reflection_state(7, now)
    state = store.get_reflection_state()

    assert state.last_seq == 7
    assert state.last_reflection_at == now
