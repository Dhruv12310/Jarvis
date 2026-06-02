"""StructuredStore goals: add/list/filter/update/complete round-trip + persistence (temp SQLite)."""

from datetime import UTC, datetime

import pytest

from jarvis.stores.sqlite_store import SQLiteStructuredStore
from jarvis.stores.structured import Goal


def _store(tmp_path):
    return SQLiteStructuredStore(tmp_path / "jarvis.db")


def test_save_goal_returns_active_goal_with_id(tmp_path):
    goal = _store(tmp_path).save_goal("learn rust")

    assert isinstance(goal, Goal)
    assert goal.id >= 1
    assert goal.description == "learn rust"
    assert goal.status == "active"
    assert goal.progress == 0.0
    assert isinstance(goal.created_at, datetime)


def test_get_goals_returns_newest_first(tmp_path):
    store = _store(tmp_path)
    store.save_goal("first")
    store.save_goal("second")

    assert [g.description for g in store.get_goals()] == ["second", "first"]


def test_get_goals_filters_by_status(tmp_path):
    store = _store(tmp_path)
    a = store.save_goal("a")
    store.save_goal("b")
    store.update_goal(a.id, status="done", progress=1.0)

    assert [g.description for g in store.get_goals(status="active")] == ["b"]
    assert [g.description for g in store.get_goals(status="done")] == ["a"]


def test_update_goal_sets_status_and_progress(tmp_path):
    store = _store(tmp_path)
    goal = store.save_goal("ship phase 2")

    updated = store.update_goal(goal.id, status="done", progress=1.0)

    assert updated.id == goal.id
    assert updated.status == "done"
    assert updated.progress == 1.0


def test_update_goal_partial_keeps_other_fields(tmp_path):
    store = _store(tmp_path)
    goal = store.save_goal("incremental")

    updated = store.update_goal(goal.id, progress=0.5)

    assert updated.progress == 0.5
    assert updated.status == "active"  # untouched


def test_update_missing_goal_raises(tmp_path):
    store = _store(tmp_path)

    with pytest.raises(LookupError):
        store.update_goal(999, status="done")


def test_save_goal_with_priority_and_deadline_round_trips(tmp_path):
    store = _store(tmp_path)
    deadline = datetime(2026, 12, 31, tzinfo=UTC)

    store.save_goal("year goal", priority="high", deadline=deadline)

    fetched = store.get_goals()[0]
    assert fetched.priority == "high"
    assert fetched.deadline == deadline


def test_goals_persist_across_store_instances(tmp_path):
    path = tmp_path / "jarvis.db"
    first = SQLiteStructuredStore(path)
    first.save_goal("durable")
    first.close()

    second = SQLiteStructuredStore(path)

    assert [g.description for g in second.get_goals()] == ["durable"]


def test_get_goals_is_empty_on_a_fresh_store(tmp_path):
    assert _store(tmp_path).get_goals() == []
