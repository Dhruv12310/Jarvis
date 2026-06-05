"""Company fundamentals connector via Finnhub (profile, basic financials, analyst trend, news).

Outbound HTTP only to Finnhub, with the EXISTING key from config (the same one markets.py uses) -
no new credential. Where markets.py answers "what's the price", this answers "what IS this company":
market cap + industry (/stock/profile2), valuation + margins + growth (/stock/metric, basic
financials), the analyst buy/hold/sell trend (/stock/recommendation), and recent company headlines
(/company-news). Each facet is a separate Item with a structured `extra`, so a missing or failing
facet just drops out - a metric outage never costs you the profile or the news. An empty key yields
no items (the view then says it could not fetch, never inventing a number). Verified free-tier on
2026-06-04: all four endpoints return 200. Fundamentals change slowly, so this is cached longer than
quotes (config.cache_ttl_fundamentals).
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import httpx

from jarvis.config import config
from jarvis.connectors.base import Connector, ConnectorResult, Item, Source

_BASE = "https://finnhub.io/api/v1"
_TICKER = re.compile(r"\b[A-Z]{1,5}\b")
# Uppercase tokens that are not tickers, so a plain question does not resolve to junk (mirrors
# markets.py; the service layer normally passes an already-resolved symbol).
_NOT_TICKERS = {"AI", "I", "A", "US", "CEO", "IPO", "ETF", "LLM", "HN", "YC", "Q1", "Q2", "Q3"}
_NEWS_LIMIT = 5
_NEWS_LOOKBACK_DAYS = 30


class FundamentalsConnector(Connector):
    name = "fundamentals"
    description = (
        "Company fundamentals and analysis: market cap, revenue, margins, P/E, 52-week range, "
        "analyst recommendations, and recent company news for a specific stock."
    )

    def __init__(self, client: httpx.Client | None = None, api_key: str | None = None) -> None:
        self._client = client or httpx.Client(timeout=10.0)
        self._api_key = api_key if api_key is not None else config.finnhub_api_key

    def fetch(self, query: str) -> ConnectorResult:
        source = Source(name="Finnhub", url="https://finnhub.io/")
        symbol = self._symbol(query)
        if not self._api_key or not symbol:
            return ConnectorResult(source=source, items=[], query=query)
        # Each facet is independent: a failed call contributes nothing rather than sinking the rest.
        items = [
            item
            for item in (
                self._profile_item(symbol),
                self._financials_item(symbol),
                self._recommendation_item(symbol),
            )
            if item is not None
        ]
        items += self._news_items(symbol)
        return ConnectorResult(source=source, items=items, query=query)

    def _symbol(self, query: str) -> str | None:
        """The first ticker-shaped token (the service usually passes a resolved symbol already)."""
        query = query.strip()
        if _TICKER.fullmatch(query):  # already a bare ticker
            return query.upper()
        named = [t for t in _TICKER.findall(query) if t not in _NOT_TICKERS]
        return named[0] if named else None

    def _get(self, path: str, params: dict) -> dict | list | None:
        """One guarded GET: the key is always sent; any non-200 / transport error -> None."""
        try:
            response = self._client.get(f"{_BASE}{path}", params={**params, "token": self._api_key})
        except httpx.HTTPError:
            return None
        if response.status_code != 200:
            return None
        try:
            return response.json()
        except ValueError:
            return None

    def _profile_item(self, symbol: str) -> Item | None:
        data = self._get("/stock/profile2", {"symbol": symbol})
        if not isinstance(data, dict) or not data.get("name"):
            return None
        market_cap = data.get("marketCapitalization")  # in millions of `currency`
        market_cap_str = _format_cap(market_cap, data.get("currency"))
        industry = data.get("finnhubIndustry") or "unknown industry"
        return Item(
            title=data.get("name") or symbol,
            detail=f"{industry}; market cap {market_cap_str}",
            url=data.get("weblink") or data.get("weburl"),
            extra={
                "kind": "profile",
                "symbol": symbol,
                "name": data.get("name"),
                "industry": data.get("finnhubIndustry"),
                "exchange": data.get("exchange"),
                "ipo": data.get("ipo"),
                "market_cap": market_cap_str,  # human-formatted ("$4.58T")
                "market_cap_millions": market_cap,
                "shares_outstanding": data.get("shareOutstanding"),
                "currency": data.get("currency"),
                "country": data.get("country"),
                "weburl": data.get("weburl"),
                "logo": data.get("logo"),
            },
        )

    def _financials_item(self, symbol: str) -> Item | None:
        data = self._get("/stock/metric", {"symbol": symbol, "metric": "all"})
        metric = data.get("metric") if isinstance(data, dict) else None
        if not isinstance(metric, dict) or not metric:
            return None

        def num(key: str) -> float | None:
            value = metric.get(key)
            return float(value) if isinstance(value, (int, float)) else None

        pe = num("peTTM")
        net_margin = num("netProfitMarginTTM")
        rev_growth = num("revenueGrowthTTMYoy")
        bits = []
        if pe is not None:
            bits.append(f"P/E {pe:.1f}")
        if net_margin is not None:
            bits.append(f"net margin {net_margin:.1f}%")
        if rev_growth is not None:
            bits.append(f"revenue growth {rev_growth:.1f}% YoY")
        return Item(
            title="Financials",
            detail=", ".join(bits) if bits else "key metrics available",
            url=None,
            extra={
                "kind": "financials",
                "symbol": symbol,
                "pe_ttm": pe,
                "ps_ttm": num("psTTM"),
                "pb": num("pbAnnual"),
                "net_margin_ttm": net_margin,
                "gross_margin_ttm": num("grossMarginTTM"),
                "operating_margin_ttm": num("operatingMarginTTM"),
                "roe_ttm": num("roeTTM"),
                "revenue_per_share_ttm": num("revenuePerShareTTM"),
                "revenue_growth_yoy": rev_growth,
                "eps_ttm": num("epsTTM"),
                "week52_high": num("52WeekHigh"),
                "week52_low": num("52WeekLow"),
                "dividend_yield": num("dividendYieldIndicatedAnnual"),
                "beta": num("beta"),
            },
        )

    def _recommendation_item(self, symbol: str) -> Item | None:
        data = self._get("/stock/recommendation", {"symbol": symbol})
        if not isinstance(data, list) or not data:
            return None
        latest = data[0]  # Finnhub returns newest period first
        if not isinstance(latest, dict):
            return None
        counts = {
            k: int(latest.get(k) or 0) for k in ("strongBuy", "buy", "hold", "sell", "strongSell")
        }
        period = latest.get("period")
        return Item(
            title="Analyst recommendation",
            detail=(
                f"strong buy {counts['strongBuy']}, buy {counts['buy']}, hold {counts['hold']}, "
                f"sell {counts['sell']}, strong sell {counts['strongSell']}"
                + (f" (as of {period})" if period else "")
            ),
            url=None,
            extra={"kind": "recommendation", "symbol": symbol, "period": period, **counts},
        )

    def _news_items(self, symbol: str) -> list[Item]:
        today = date.today()
        data = self._get(
            "/company-news",
            {
                "symbol": symbol,
                "from": (today - timedelta(days=_NEWS_LOOKBACK_DAYS)).isoformat(),
                "to": today.isoformat(),
            },
        )
        if not isinstance(data, list):
            return []
        items: list[Item] = []
        for article in data[:_NEWS_LIMIT]:
            if not isinstance(article, dict) or not article.get("headline"):
                continue
            outlet = article.get("source") or "unknown source"
            items.append(
                Item(
                    title=article.get("headline"),
                    detail=outlet,
                    url=article.get("url"),
                    extra={
                        "kind": "news",
                        "symbol": symbol,
                        "source": outlet,
                        "datetime": article.get("datetime"),
                        "summary": article.get("summary"),
                    },
                )
            )
        return items


def _format_cap(market_cap_millions, currency: str | None) -> str:
    """Human market cap from Finnhub's value-in-millions (e.g. 4577902.5 -> '$4.58T')."""
    if not isinstance(market_cap_millions, (int, float)) or market_cap_millions <= 0:
        return "n/a"
    prefix = "$" if (currency or "USD") == "USD" else ""
    value = float(market_cap_millions) * 1_000_000
    for threshold, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if value >= threshold:
            return f"{prefix}{value / threshold:.2f}{suffix}"
    return f"{prefix}{value:,.0f}"
