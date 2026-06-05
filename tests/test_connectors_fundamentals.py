"""FundamentalsConnector: Finnhub profile/financials/recommendation/news -> Items. Offline."""

import httpx

from jarvis.connectors.fundamentals import FundamentalsConnector, _format_cap

_PROFILE = {
    "name": "Apple Inc",
    "ticker": "AAPL",
    "finnhubIndustry": "Technology",
    "exchange": "NASDAQ",
    "ipo": "1980-12-12",
    "marketCapitalization": 4577902.5,  # millions -> $4.58T
    "shareOutstanding": 14840.0,
    "currency": "USD",
    "country": "US",
    "weburl": "https://www.apple.com/",
    "logo": "https://logo.png",
}
_METRIC = {
    "metric": {
        "peTTM": 37.35,
        "netProfitMarginTTM": 27.15,
        "grossMarginTTM": 47.86,
        "revenuePerShareTTM": 30.66,
        "revenueGrowthTTMYoy": 12.76,
        "epsTTM": 8.27,
        "52WeekHigh": 316.94,
        "52WeekLow": 195.07,
        "beta": 1.09,
    }
}
_RECOMMENDATION = [
    {"strongBuy": 12, "buy": 20, "hold": 8, "sell": 1, "strongSell": 0, "period": "2026-06-01"},
    {"strongBuy": 10, "buy": 18, "hold": 9, "sell": 2, "strongSell": 0, "period": "2026-05-01"},
]
_NEWS = [
    {
        "headline": "Apple unveils new chip",
        "source": "Reuters",
        "url": "https://r/1",
        "datetime": 1,
        "summary": "s1",
    },
    {
        "headline": "Apple partners with X",
        "source": "Bloomberg",
        "url": "https://b/2",
        "datetime": 2,
        "summary": "s2",
    },
]


def _handler_all(request):
    assert request.url.params.get("token")  # the key is always sent
    path = request.url.path
    if path.endswith("/stock/profile2"):
        return httpx.Response(200, json=_PROFILE)
    if path.endswith("/stock/metric"):
        return httpx.Response(200, json=_METRIC)
    if path.endswith("/stock/recommendation"):
        return httpx.Response(200, json=_RECOMMENDATION)
    if path.endswith("/company-news"):
        return httpx.Response(200, json=_NEWS)
    return httpx.Response(404, json={})


def _connector(handler=_handler_all, api_key="testkey"):
    return FundamentalsConnector(
        client=httpx.Client(transport=httpx.MockTransport(handler)), api_key=api_key
    )


def test_all_facets_become_items():
    items = _connector().fetch("AAPL").items
    by_kind = {i.extra["kind"]: i for i in items}

    assert set(by_kind) == {"profile", "financials", "recommendation", "news"}
    assert by_kind["profile"].title == "Apple Inc"
    assert by_kind["profile"].extra["market_cap_millions"] == 4577902.5
    assert "$4.58T" in by_kind["profile"].detail
    assert by_kind["financials"].extra["pe_ttm"] == 37.35
    assert "P/E 37.4" in by_kind["financials"].detail  # 37.35 -> 37.4 at one decimal
    assert by_kind["recommendation"].extra["strongBuy"] == 12  # newest period wins
    assert "(as of 2026-06-01)" in by_kind["recommendation"].detail


def test_news_capped_and_structured():
    news = [i for i in _connector().fetch("AAPL").items if i.extra["kind"] == "news"]

    assert [i.title for i in news] == ["Apple unveils new chip", "Apple partners with X"]
    assert news[0].url == "https://r/1"
    assert news[0].detail == "Reuters"


def test_no_key_returns_no_items():
    assert _connector(api_key="").fetch("AAPL").items == []


def test_blank_or_unresolvable_query_returns_no_items():
    # No ticker-shaped token -> nothing to look up (the service resolves names before calling).
    assert _connector().fetch("tell me about this company").items == []


def test_failed_facet_degrades_to_partial():
    # The metric endpoint 500s; profile / recommendation / news still come back.
    def handler(request):
        if request.url.path.endswith("/stock/metric"):
            return httpx.Response(500, json={})
        return _handler_all(request)

    kinds = {i.extra["kind"] for i in _connector(handler).fetch("AAPL").items}

    assert "financials" not in kinds  # the failed facet drops out
    assert {"profile", "recommendation", "news"} <= kinds  # the rest survive


def test_empty_profile_skips_profile_only():
    def handler(request):
        if request.url.path.endswith("/stock/profile2"):
            return httpx.Response(200, json={})  # no "name" -> not a valid profile
        return _handler_all(request)

    kinds = {i.extra["kind"] for i in _connector(handler).fetch("AAPL").items}

    assert "profile" not in kinds
    assert "financials" in kinds


def test_name_and_description():
    connector = _connector()
    assert connector.name == "fundamentals"
    assert "market cap" in connector.description.lower()


def test_format_cap_units():
    assert _format_cap(4577902.5, "USD") == "$4.58T"
    assert _format_cap(50_000, "USD") == "$50.00B"
    assert _format_cap(250, "USD") == "$250.00M"
    assert _format_cap(0, "USD") == "n/a"
    assert _format_cap(None, "USD") == "n/a"
