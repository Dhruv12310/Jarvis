"""JarvisService.news(): deterministic GDELT/GNews -> NewsItem mapping, no signal. Offline."""

from jarvis.connectors.base import ConnectorResult, Item, Source
from jarvis.results import NewsItem
from jarvis.service import JarvisService


class _FakeConn:
    def __init__(self, name, items):
        self.name = name
        self.description = name
        self._items = items
        self.queried: list[str] = []

    def fetch(self, query):
        self.queried.append(query)
        return ConnectorResult(source=Source(name=self.name), items=self._items, query=query)


class _Signals:
    def __init__(self):
        self.emitted = []

    def emit(self, kind, payload):
        self.emitted.append((kind, payload))


def _service(connectors):
    signals = _Signals()
    svc = JarvisService(
        orchestrator=None,
        knowledge=None,
        store=None,
        memory=None,
        signals=signals,
        source="test",
        connectors=connectors,
    )
    return svc, signals


def _gdelt_item(title, country, seendate="20260604T120000Z", url=None):
    return Item(
        title=title,
        detail="reuters.com",
        url=url or f"https://r/{title.replace(' ', '')}",
        extra={
            "kind": "news",
            "source": "reuters.com",
            "country": country,
            "seendate": seendate,
            "image": "https://img/x.jpg",
        },
    )


def test_news_maps_country_and_published_and_emits_no_signal():
    svc, signals = _service(
        {"gdelt": _FakeConn("gdelt", [_gdelt_item("Talks resume", "United States")])}
    )

    items = svc.news("world")

    assert isinstance(items[0], NewsItem)
    assert items[0].country == "United States"
    assert items[0].published == "2026-06-04"
    assert items[0].source == "reuters.com"
    assert signals.emitted == []  # READ-ONLY inspector: zero signals


def test_news_dedups_by_url_or_title():
    dup = _gdelt_item("Same story", "France", url="https://r/same")
    svc, _ = _service({"gdelt": _FakeConn("gdelt", [dup, dup])})
    assert len(svc.news("x")) == 1


def test_news_merges_gdelt_and_gnews_without_country():
    gdelt = _FakeConn("gdelt", [_gdelt_item("World event", "India")])
    gnews = _FakeConn(
        "news",
        [
            Item(
                title="US headline",
                detail="AP",
                url="https://r/us",
                extra={"source": "AP", "published_at": "2026-06-03T10:00:00Z"},
            )
        ],
    )
    svc, _ = _service({"gdelt": gdelt, "news": gnews})

    items = svc.news("x")

    assert [i.country for i in items] == ["India", None]  # GNews item has no globe pin
    assert items[1].published == "2026-06-03"  # derived from published_at


def test_news_default_query_never_raises_on_empty():
    svc, _ = _service({})
    assert svc.news() == []


def test_news_swallows_a_failing_connector():
    class _Boom:
        def fetch(self, query):
            raise RuntimeError("gdelt 429")

    svc, _ = _service({"gdelt": _Boom()})
    assert svc.news("x") == []  # _fetch swallows -> empty, never raises
