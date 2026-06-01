"""CachingConnector: a cache hit skips the inner connector and reconstructs the result.

A fake in-memory cache (controllable freshness) plus a call-counting inner connector. The
serialize/deserialize round-trip is exercised implicitly: a cache hit reconstructs an equal result.
"""

from jarvis.cache.base import Cache
from jarvis.connectors.base import Connector, ConnectorResult, Item, Source
from jarvis.connectors.caching import CachingConnector


class _CountingConnector(Connector):
    name = "fake"
    description = "a fake source for tests"

    def __init__(self):
        self.calls = 0

    def fetch(self, query):
        self.calls += 1
        return ConnectorResult(
            source=Source(name="Fake", url="https://example.test"),
            items=[Item(title="hello", detail="d", url="https://x.test", extra={"n": 1})],
            query=query,
        )


class _DictCache(Cache):
    def __init__(self, *, expired=False):
        self.store = {}
        self.expired = expired

    def get(self, key):
        return None if self.expired else self.store.get(key)

    def set(self, key, value, ttl_seconds):
        self.store[key] = value


def test_cache_hit_skips_inner_and_reconstructs_result():
    inner = _CountingConnector()
    cc = CachingConnector(inner, _DictCache(), ttl_seconds=300)

    first = cc.fetch("ai")
    second = cc.fetch("ai")

    assert inner.calls == 1  # second served from cache
    assert second == first  # frozen dataclasses compare by value after the round-trip
    assert second.items[0].extra == {"n": 1}


def test_miss_or_expiry_refetches():
    inner = _CountingConnector()
    cc = CachingConnector(inner, _DictCache(expired=True), ttl_seconds=300)

    cc.fetch("q")
    cc.fetch("q")

    assert inner.calls == 2


def test_last_was_cache_hit_flag_tracks_source():
    cc = CachingConnector(_CountingConnector(), _DictCache(), ttl_seconds=300)

    cc.fetch("q")
    assert cc.last_was_cache_hit is False  # first time: miss
    cc.fetch("q")
    assert cc.last_was_cache_hit is True  # second time: served from cache


def test_caching_connector_exposes_inner_identity():
    cc = CachingConnector(_CountingConnector(), _DictCache(), ttl_seconds=300)
    assert cc.name == "fake"
    assert "fake source" in cc.description
