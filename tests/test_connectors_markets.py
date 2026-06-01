"""MarketsConnector: Finnhub quotes -> movers ranked by absolute percent change. Offline."""

import httpx

from jarvis.connectors.markets import MarketsConnector

_QUOTES = {
    "AAPL": {"c": 200.0, "d": 2.0, "dp": 1.0, "pc": 198.0, "t": 0},
    "NVDA": {"c": 110.0, "d": -10.0, "dp": -8.33, "pc": 120.0, "t": 0},
    "MSFT": {"c": 400.0, "d": 1.0, "dp": 0.25, "pc": 399.0, "t": 0},
}


def _handler(request):
    symbol = request.url.params.get("symbol")
    assert request.url.params.get("token")  # the key is always sent
    return httpx.Response(200, json=_QUOTES.get(symbol, {"c": 0, "dp": 0, "pc": 0}))


def _connector(api_key="testkey"):
    transport = httpx.MockTransport(_handler)
    return MarketsConnector(client=httpx.Client(transport=transport), api_key=api_key)


def test_named_tickers_ranked_by_absolute_percent_change():
    result = _connector().fetch("how are AAPL NVDA MSFT doing")

    assert result.source.name == "Finnhub"
    assert [i.title for i in result.items] == ["NVDA", "AAPL", "MSFT"]  # |8.33| > |1.0| > |0.25|
    assert result.items[0].extra["change_pct"] == -8.33
    assert "to $110.00" in result.items[0].detail
    assert result.items[1].detail.startswith("+1.00%")


def test_no_key_returns_no_items():
    assert _connector(api_key="").fetch("what moved today").items == []


def test_falls_back_to_watchlist_when_no_tickers_named():
    # No uppercase tickers in the query -> the configured watchlist is used; unknown symbols
    # (c == 0) are dropped, leaving the three the fixture knows about.
    titles = [i.title for i in _connector().fetch("what moved in the market today").items]

    assert "AAPL" in titles
    assert "NVDA" in titles


def test_name_and_description():
    connector = _connector()
    assert connector.name == "markets"
    assert "percent change" in connector.description.lower()
