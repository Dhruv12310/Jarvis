"""Feedback reward (§7.5) - the §8 contract made code: genuine value, never attention."""

from datetime import UTC, datetime

from jarvis.proactivity.feedback import reward
from jarvis.stores.sqlite_store import SQLiteStructuredStore
from jarvis.stores.structured import Outcome


def test_reward_encodes_value_never_attention():
    assert reward("more_like_this") == 1.0  # explicit helpful is positive
    assert reward("acted") == 0.0  # §8: acted ALONE is non-positive (a tap is not confirmed value)
    assert reward("acted", corroborated=True) > 0  # corroborated by a real good outcome -> positive
    assert reward("dismissed") < 0
    assert reward("less_like_this") < 0
    assert reward("ignored") == 0.0  # neutral - attention is never a positive reward


def test_outcome_store_round_trips(tmp_path):
    store = SQLiteStructuredStore(tmp_path / "j.db")
    ts = datetime(2026, 6, 4, 9, 0, tzinfo=UTC)
    store.save_outcome(Outcome(suggestion_id="abc", ts=ts, result="more_like_this"))
    store.save_outcome(Outcome(suggestion_id="def", ts=ts, result="dismissed"))

    outcomes = store.get_outcomes()

    assert {(o.suggestion_id, o.result) for o in outcomes} == {
        ("abc", "more_like_this"),
        ("def", "dismissed"),
    }
