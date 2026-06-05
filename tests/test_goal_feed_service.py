"""JarvisService.goal_feed(): the deterministic PULL view that ties active goals to public info.

Fakes for store/connector/knowledge/signals - no LLM, network, or real store. Asserts: one entry
per active goal, deterministic WHY, the per-goal cap, attached standing suggestions, exactly one
metadata-only signal, and that failures degrade to [] without raising.
"""

from datetime import UTC, datetime

from jarvis.config import config
from jarvis.connectors.base import ConnectorResult, Item, Source
from jarvis.service import JarvisService
from jarvis.stores.structured import Goal, Suggestion


def _goal(gid, desc):
    return Goal(
        id=gid,
        description=desc,
        status="active",
        progress=0.0,
        priority="medium",
        deadline=None,
        created_at=datetime(2026, 6, 1, tzinfo=UTC),
    )


class _StubConn:
    def __init__(self, items):
        self._items = items

    def fetch(self, query):
        return ConnectorResult(source=Source(name="x"), items=self._items, query=query)


class _BadConn:
    def fetch(self, query):
        raise RuntimeError("api 500")


class _FakeStore:
    def __init__(self, goals, suggestions=()):
        self._goals, self._suggestions = goals, list(suggestions)

    def get_goals(self, status=None):
        return [g for g in self._goals if status is None or g.status == status]

    def get_recent_suggestions(self, *, since):
        return self._suggestions


class _RecSignals:
    def __init__(self):
        self.events = []

    def emit(self, kind, data):
        self.events.append((kind, data))


class _NoKnowledge:
    def ask(self, query):
        return None  # no connector applies -> no grounded snippet


def _service(store, *, connectors=None, knowledge=None, signals=None):
    return JarvisService(
        orchestrator=None,
        knowledge=knowledge or _NoKnowledge(),
        store=store,
        memory=None,
        signals=signals or _RecSignals(),
        source="web",
        llm=None,
        connectors=connectors or {},
    )


def test_feed_has_one_entry_per_active_goal():
    store = _FakeStore([_goal(1, "track NVDA"), _goal(2, "learn rust")])
    feeds = _service(store).goal_feed()
    assert [f.goal_id for f in feeds] == [1, 2]
    assert feeds[0].goal == "track NVDA"


def test_markets_item_attached_for_ticker_goal_with_deterministic_why():
    item = Item(
        title="NVDA",
        detail="+2.30% to $1000.00 (prev $977.00)",
        url="https://finance.yahoo.com/quote/NVDA",
        extra={"change_pct": 2.3, "price": 1000.0, "prev_close": 977.0},
    )
    store = _FakeStore([_goal(1, "grow NVDA position")])
    feeds = _service(store, connectors={"markets": _StubConn([item])}).goal_feed()
    surfaced = feeds[0].items[0]
    assert surfaced.source == "markets" and surfaced.title == "NVDA"
    assert surfaced.why.startswith("relates to goal #1: grow NVDA position")
    assert "matched 'NVDA'" in surfaced.why


def test_topic_goal_is_non_empty_via_news():
    item = Item(title="Rust 2.0 ships", detail="big release", url="https://news/1", extra={})
    store = _FakeStore([_goal(1, "learn rust")])  # no ticker -> news/hn path
    feeds = _service(store, connectors={"news": _StubConn([item])}).goal_feed()
    assert feeds[0].items  # the user finally SEES goal-driven info
    assert feeds[0].items[0].source == "news"


def test_per_goal_cap_limits_fetched_items():
    items = [Item(title=f"H{i}", detail="d", url=f"u{i}", extra={}) for i in range(10)]
    store = _FakeStore([_goal(1, "renewable energy news")])
    svc = _service(store, connectors={"news": _StubConn(items), "hn": _StubConn(items)})
    feeds = svc.goal_feed()
    assert 0 < len(feeds[0].items) <= config.goal_feed_per_goal_cap  # never the full 20


def test_standing_suggestion_for_goal_is_attached_and_not_capped_away():
    sug = Suggestion(
        id="s1",
        created_at=datetime.now(UTC),
        candidate_type="goal_nudge",
        entity_key="goal:1",
        content="Goal #1 is due soon.",
        why="deadline near",
        source_ids=["goal:1"],
        topics=["x"],
        features={},
        score=2.0,
        surfaced=True,
        channel="feed",
    )
    items = [Item(title=f"H{i}", detail="d", url=f"u{i}", extra={}) for i in range(10)]
    store = _FakeStore([_goal(1, "ship feature")], suggestions=[sug])
    feeds = _service(store, connectors={"news": _StubConn(items)}).goal_feed()
    assert "suggestion" in [i.kind for i in feeds[0].items]  # owned context survives the cap


def test_emits_exactly_one_metadata_only_signal():
    sigs = _RecSignals()
    store = _FakeStore([_goal(1, "track NVDA")])
    _service(store, signals=sigs).goal_feed()
    goal_feed_events = [e for e in sigs.events if e[0] == "goal_feed"]
    assert len(goal_feed_events) == 1
    _kind, data = goal_feed_events[0]
    assert set(data) >= {"source", "goals", "items"}
    assert data["source"] == "web" and data["goals"] == 1
    assert "track NVDA" not in str(data)  # NO goal description / content in the signal


def test_never_raises_when_store_fails_signal_still_emitted():
    class _Boom(_FakeStore):
        def get_goals(self, status=None):
            raise RuntimeError("db down")

    sigs = _RecSignals()
    feeds = _service(_Boom([]), signals=sigs).goal_feed()
    assert feeds == []
    assert any(e[0] == "goal_feed" for e in sigs.events)  # one signal even on failure


def test_connector_failure_degrades_to_no_items_for_that_goal():
    store = _FakeStore([_goal(1, "track NVDA")])
    feeds = _service(store, connectors={"markets": _BadConn()}).goal_feed()
    assert feeds[0].items == []  # _fetch swallows -> empty, no raise
