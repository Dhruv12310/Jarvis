"""CachingConnector: wrap any Connector with a TTL cache (decorator pattern).

Written once here instead of in every connector. A cache hit skips the inner fetch entirely, which
is what respects the upstream API rate limits. The cache key is ``name:normalized-query`` — never an
API key. ``last_was_cache_hit`` lets the CLI show a ``(cached)`` marker.
"""

from __future__ import annotations

from jarvis.cache.base import Cache
from jarvis.connectors.base import (
    Connector,
    ConnectorResult,
    deserialize_result,
    serialize_result,
)


class CachingConnector(Connector):
    def __init__(self, inner: Connector, cache: Cache, ttl_seconds: int) -> None:
        self._inner = inner
        self._cache = cache
        self._ttl = ttl_seconds
        self._last_hit = False

    @property
    def name(self) -> str:
        return self._inner.name

    @property
    def description(self) -> str:
        return self._inner.description

    @property
    def last_was_cache_hit(self) -> bool:
        return self._last_hit

    def __getattr__(self, attr: str):
        # Transparent decorator: surface any extra capability the wrapped connector defines but this
        # generic cache does not itself override (e.g. MarketsConnector.search). __getattr__ only
        # fires for attributes missing on this object; guard _inner so a half-built instance can't
        # recurse forever. Cached fetch() and the declared properties above shadow this untouched.
        if attr == "_inner":
            raise AttributeError(attr)
        return getattr(self._inner, attr)

    def fetch(self, query: str) -> ConnectorResult:
        key = f"{self._inner.name}:{query.strip().lower()}"
        cached = self._cache.get(key)
        if cached is not None:
            self._last_hit = True
            return deserialize_result(cached)
        self._last_hit = False
        result = self._inner.fetch(query)
        self._cache.set(key, serialize_result(result), self._ttl)
        return result
