"""News connector via GNews /search.

Outbound HTTP only to GNews. The API key (apikey param) comes from config and is never logged or put
in a cache key. Verified from the docs: articles have title, description, url, publishedAt, and a
nested source.name. An empty key or a non-200 response (for example an unactivated account) yields
no items, so the answerer says it could not fetch rather than inventing headlines.
"""

from __future__ import annotations

import httpx

from jarvis.config import config
from jarvis.connectors.base import Connector, ConnectorResult, Item, Source

_SEARCH_URL = "https://gnews.io/api/v4/search"


class NewsConnector(Connector):
    name = "news"
    description = "Current news headlines: world affairs, business, and AI/technology."

    def __init__(
        self,
        client: httpx.Client | None = None,
        api_key: str | None = None,
        max_results: int = 5,
    ) -> None:
        self._client = client or httpx.Client(timeout=10.0)
        self._api_key = api_key if api_key is not None else config.gnews_api_key
        self._max = max_results

    def fetch(self, query: str) -> ConnectorResult:
        source = Source(name="GNews", url="https://gnews.io/")
        if not self._api_key:
            return ConnectorResult(source=source, items=[], query=query)
        response = self._client.get(
            _SEARCH_URL,
            params={"q": query, "apikey": self._api_key, "max": self._max, "lang": "en"},
        )
        if response.status_code != 200:
            return ConnectorResult(source=source, items=[], query=query)
        articles = response.json().get("articles", [])
        return ConnectorResult(
            source=source, items=[self._to_item(a) for a in articles], query=query
        )

    @staticmethod
    def _to_item(article: dict) -> Item:
        outlet = (article.get("source") or {}).get("name") or "unknown source"
        published = (article.get("publishedAt") or "")[:10]  # YYYY-MM-DD
        return Item(
            title=article.get("title") or "(untitled)",
            detail=outlet if not published else f"{outlet}, {published}",
            url=article.get("url"),
            extra={
                "source": outlet,
                "published_at": article.get("publishedAt"),
                "description": article.get("description"),
            },
        )
