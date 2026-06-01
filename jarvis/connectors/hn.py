"""Hacker News / YC connector via the keyless Algolia HN Search API.

The only outbound HTTP here is to the public Algolia endpoint (no API key). Verified live against
https://hn.algolia.com/api/v1/search: params query/tags/hitsPerPage; hit fields title, url (null
for text posts), points, num_comments, author, objectID, created_at.
"""

from __future__ import annotations

import httpx

from jarvis.connectors.base import Connector, ConnectorResult, Item, Source

_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
_ITEM_URL = "https://news.ycombinator.com/item?id={object_id}"


class HackerNewsConnector(Connector):
    name = "hn"
    description = "Hacker News and Y Combinator: tech, startups, AI, and software stories."

    def __init__(self, client: httpx.Client | None = None, hits: int = 5) -> None:
        self._client = client or httpx.Client(timeout=10.0)
        self._hits = hits

    def fetch(self, query: str) -> ConnectorResult:
        response = self._client.get(
            _SEARCH_URL,
            params={"query": query, "tags": "story", "hitsPerPage": self._hits},
        )
        response.raise_for_status()
        hits = response.json().get("hits", [])
        return ConnectorResult(
            source=Source(name="Hacker News (Algolia)", url="https://news.ycombinator.com/"),
            items=[self._to_item(hit) for hit in hits],
            query=query,
        )

    @staticmethod
    def _to_item(hit: dict) -> Item:
        object_id = str(hit.get("objectID", ""))
        points = hit.get("points") or 0
        comments = hit.get("num_comments") or 0
        return Item(
            title=hit.get("title") or "(untitled)",
            detail=f"{points} points, {comments} comments",
            url=hit.get("url") or _ITEM_URL.format(object_id=object_id),
            extra={
                "points": points,
                "num_comments": comments,
                "author": hit.get("author"),
                "object_id": object_id,
                "created_at": hit.get("created_at"),
            },
        )
