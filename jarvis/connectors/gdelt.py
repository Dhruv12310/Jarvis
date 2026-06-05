"""Global news connector via the GDELT DOC 2.0 API (worldwide events, geopolitics, conflicts).

Outbound HTTP only to GDELT. KEYLESS - GDELT is a free public firehose, so (unlike markets/news)
there is no credential to gate on; failure just yields no items. Where GNews gives a handful of
curated English headlines, GDELT spans worldwide media in every language - which is what makes it
the right source for global/conflict situational awareness. Two consequences shape this connector:
results are multilingual (so it filters to English by default - a Russian headline is noise to an
English reader), and GDELT rate-limits bursts hard with HTTP 429 (so a non-200 degrades to no items
and the TTL cache, config.cache_ttl_gdelt, absorbs the rest). Verified live 2026-06-04: artlist
JSON returns articles with url/title/seendate/domain/language/sourcecountry.
"""

from __future__ import annotations

import httpx

from jarvis.connectors.base import Connector, ConnectorResult, Item, Source
from jarvis.query import keywords

_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
# GDELT is multilingual; over-fetch then keep the top English ones, so the English cap is still met.
_OVERFETCH = 30
# A conversational question reduces to "" keywords; GDELT still needs a query, so cast a broad world
# net for the "what's happening globally" case (a specific subject keeps its own terms).
_BROAD = "(world OR international OR conflict OR election OR economy)"


class GdeltConnector(Connector):
    name = "gdelt"
    description = (
        "Global and world news from worldwide media: geopolitics, conflicts, international "
        "affairs, and breaking world events (broad coverage beyond US/English-only sources)."
    )

    def __init__(
        self,
        client: httpx.Client | None = None,
        max_results: int = 8,
        timespan: str = "3d",
        english_only: bool = True,
    ) -> None:
        # A descriptive UA is courteous to a free public API and avoids looking like an anon bot.
        self._client = client or httpx.Client(
            timeout=15.0, headers={"User-Agent": "jarvis/0.1 (personal assistant)"}
        )
        self._max = max_results
        self._timespan = timespan
        self._english_only = english_only

    def fetch(self, query: str) -> ConnectorResult:
        source = Source(name="GDELT", url="https://www.gdeltproject.org/")
        query = query.strip()
        if not query:
            return ConnectorResult(source=source, items=[], query=query)
        terms = keywords(query) or _BROAD  # specific subject, else a broad world-events query
        try:
            response = self._client.get(
                _URL,
                params={
                    "query": terms,
                    "mode": "artlist",
                    "format": "json",
                    "maxrecords": str(_OVERFETCH),
                    "timespan": self._timespan,
                    "sort": "datedesc",
                },
            )
        except httpx.HTTPError:
            return ConnectorResult(source=source, items=[], query=query)
        if response.status_code != 200:  # 429 (rate limit) and any error -> no items, never raises
            return ConnectorResult(source=source, items=[], query=query)
        try:
            articles = response.json().get("articles", [])
        except ValueError:
            return ConnectorResult(source=source, items=[], query=query)
        items: list[Item] = []
        for article in articles:
            if not isinstance(article, dict) or not article.get("title"):
                continue
            if self._english_only and (article.get("language") or "").lower() != "english":
                continue
            items.append(self._to_item(article))
            if len(items) >= self._max:
                break
        return ConnectorResult(source=source, items=items, query=query)

    @staticmethod
    def _to_item(article: dict) -> Item:
        domain = article.get("domain") or "unknown source"
        seen = article.get("seendate") or ""  # GDELT format: YYYYMMDDTHHMMSSZ
        published = f"{seen[0:4]}-{seen[4:6]}-{seen[6:8]}" if len(seen) >= 8 else ""
        return Item(
            title=article.get("title"),
            detail=domain if not published else f"{domain}, {published}",
            url=article.get("url"),
            extra={
                "kind": "news",
                "source": domain,
                "language": article.get("language"),
                "country": article.get("sourcecountry"),
                "seendate": seen,
                "image": article.get("socialimage"),
            },
        )
