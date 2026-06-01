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


def test_symbol_dropped_on_non_200():
    def handler(request):
        symbol = request.url.params.get("symbol")
        if symbol == "NVDA":
            return httpx.Response(500, json={})
        return httpx.Response(200, json=_QUOTES.get(symbol, {"c": 0, "dp": 0, "pc": 0}))

    connector = MarketsConnector(
        client=httpx.Client(transport=httpx.MockTransport(handler)), api_key="k"
    )
    titles = [i.title for i in connector.fetch("AAPL NVDA MSFT").items]

    assert "NVDA" not in titles  # dropped on the 500
    assert "AAPL" in titles
    assert "MSFT" in titles


def test_zero_change_ranks_last_and_no_symbol_dropped():
    quotes = {
        "AAA": {"c": 100.0, "dp": 1.5, "pc": 98.5},
        "BBB": {"c": 100.0, "dp": -1.5, "pc": 101.5},
        "CCC": {"c": 100.0, "dp": 0.0, "pc": 100.0},
    }

    def handler(request):
        return httpx.Response(200, json=quotes.get(request.url.params.get("symbol"), {"c": 0}))

    connector = MarketsConnector(
        client=httpx.Client(transport=httpx.MockTransport(handler)), api_key="k"
    )
    items = connector.fetch("AAA BBB CCC").items

    assert {i.title for i in items} == {"AAA", "BBB", "CCC"}  # none dropped
    assert items[-1].title == "CCC"  # zero change ranks last
    assert items[-1].detail.startswith("+0.00%")


def test_malformed_quote_json_drops_named_symbol():
    connector = MarketsConnector(
        client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))),
        api_key="k",
    )
    assert connector.fetch("AAPL").items == []
