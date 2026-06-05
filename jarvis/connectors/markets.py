"""Markets connector via Finnhub /quote (one call per symbol).

Outbound HTTP only to Finnhub. The API key comes from config and is never logged or put in a cache
key. "Movers" = the configured watchlist (plus any tickers named in the query) ranked by absolute
percent change. Verified live: /quote returns c (current), d (change), dp (percent), h/l/o/pc/t; an
unknown symbol comes back with c == 0. An empty key yields no items (the answerer then says it could
not fetch, never inventing prices).
"""

from __future__ import annotations

import re

import httpx

from jarvis.config import config
from jarvis.connectors.base import Connector, ConnectorResult, Item, Source

_QUOTE_URL = "https://finnhub.io/api/v1/quote"
_SEARCH_URL = "https://finnhub.io/api/v1/search"
_TICKER = re.compile(r"\b[A-Z]{1,5}\b")
# Uppercase tokens that are not tickers, so a normal question does not spawn junk lookups.
_NOT_TICKERS = {"AI", "I", "A", "US", "CEO", "IPO", "ETF", "LLM", "HN", "YC", "Q1", "Q2", "Q3"}


class MarketsConnector(Connector):
    name = "markets"
    description = "Stock market quotes and movers (price and percent change) for major tickers."

    def __init__(self, client: httpx.Client | None = None, api_key: str | None = None) -> None:
        self._client = client or httpx.Client(timeout=10.0)
        self._api_key = api_key if api_key is not None else config.finnhub_api_key

    def fetch(self, query: str) -> ConnectorResult:
        source = Source(name="Finnhub", url="https://finnhub.io/")
        if not self._api_key:
            return ConnectorResult(source=source, items=[], query=query)
        quotes = [(symbol, self._quote(symbol)) for symbol in self._symbols(query)]
        quotes = [(symbol, q) for symbol, q in quotes if q is not None]
        quotes.sort(key=lambda sq: abs(sq[1].get("dp") or 0.0), reverse=True)
        return ConnectorResult(
            source=source, items=[self._to_item(s, q) for s, q in quotes], query=query
        )

    def _symbols(self, query: str) -> list[str]:
        named = [t for t in _TICKER.findall(query) if t not in _NOT_TICKERS]
        return named or list(config.market_watchlist)

    def _quote(self, symbol: str) -> dict | None:
        response = self._client.get(_QUOTE_URL, params={"symbol": symbol, "token": self._api_key})
        if response.status_code != 200:
            return None
        data = response.json()
        return data if data.get("c") else None  # c == 0 means the symbol is unknown

    @staticmethod
    def _to_item(symbol: str, quote: dict) -> Item:
        price = quote.get("c") or 0.0
        change_pct = quote.get("dp") or 0.0
        prev = quote.get("pc") or 0.0
        sign = "+" if change_pct >= 0 else ""
        return Item(
            title=symbol,
            detail=f"{sign}{change_pct:.2f}% to ${price:.2f} (prev ${prev:.2f})",
            url=f"https://finance.yahoo.com/quote/{symbol}",
            extra={"change_pct": change_pct, "price": price, "prev_close": prev},
        )

    def search(self, query: str, limit: int = 8) -> list[tuple[str, str]]:
        """Resolve free text (a company NAME or a ticker) to candidate (symbol, description) pairs
        via Finnhub /search, so the cockpit can track a company typed by name. Ranked by relevance
        to the query (exact ticker, then ticker-prefix, then a description that STARTS with the
        query), then plain US listings over suffixed/derivative ones - so 'apple' surfaces AAPL,
        not a pineapple company. Empty on no key / blank query / non-200 / transport error - it
        never invents a symbol. Outbound HTTP stays inside the connector (the trust boundary)."""
        query = query.strip()
        if not self._api_key or not query:
            return []
        try:
            response = self._client.get(_SEARCH_URL, params={"q": query, "token": self._api_key})
        except httpx.HTTPError:
            return []
        if response.status_code != 200:
            return []
        results = response.json().get("result") or []
        ranked = sorted(results, key=lambda r: self._search_rank(r, query))
        out: list[tuple[str, str]] = []
        for result in ranked:
            symbol = (result.get("symbol") or "").strip()
            description = (result.get("description") or "").strip()
            if symbol:
                out.append((symbol, description))
            if len(out) >= limit:
                break
        return out

    @staticmethod
    def _search_rank(result: dict, query: str) -> tuple:
        symbol = result.get("symbol") or ""
        description = result.get("description") or ""
        q_upper, q_lower = query.strip().upper(), query.strip().lower()
        # Relevance to the query first (a substring match like 'pineapple' must NOT beat a name
        # match): exact ticker -> ticker-prefix -> description-starts-with -> anything. Then plain
        # US listings (no exchange suffix), common stock, shorter symbols. sorted() is stable, so
        # equal keys keep Finnhub's own relevance order. Deterministic - no LLM, no extra network.
        if symbol.upper() == q_upper:
            relevance = 0
        elif symbol.upper().startswith(q_upper):
            relevance = 1
        elif description.lower().startswith(q_lower):
            relevance = 2
        else:
            relevance = 3
        suffixed = "." in symbol or ":" in symbol
        return (relevance, suffixed, result.get("type") != "Common Stock", len(symbol))
