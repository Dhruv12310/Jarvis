"""GdeltConnector: GDELT DOC 2.0 artlist -> English news Items. Offline (keyless API mocked)."""

import httpx

from jarvis.connectors.gdelt import GdeltConnector

_ARTICLES = {
    "articles": [
        {
            "url": "https://reuters.com/a",
            "title": "Ceasefire talks resume",
            "seendate": "20260604T233000Z",
            "domain": "reuters.com",
            "language": "English",
            "sourcecountry": "United States",
            "socialimage": "https://img/a.jpg",
        },
        {
            "url": "https://9tv.co.il/b",
            "title": "Заголовок на русском",
            "seendate": "20260604T120000Z",
            "domain": "9tv.co.il",
            "language": "Russian",
            "sourcecountry": "Israel",
        },
        {
            "url": "https://bbc.com/c",
            "title": "Summit reaches accord",
            "seendate": "20260603T080000Z",
            "domain": "bbc.com",
            "language": "English",
            "sourcecountry": "United Kingdom",
        },
    ]
}


def _connector(handler, **kwargs):
    return GdeltConnector(client=httpx.Client(transport=httpx.MockTransport(handler)), **kwargs)


def _ok(_request):
    return httpx.Response(200, json=_ARTICLES)


def test_maps_english_articles_to_items():
    items = _connector(_ok).fetch("world news").items

    assert [i.title for i in items] == ["Ceasefire talks resume", "Summit reaches accord"]
    assert items[0].url == "https://reuters.com/a"
    assert items[0].detail == "reuters.com, 2026-06-04"  # domain + parsed seendate
    assert items[0].extra["country"] == "United States"
    assert items[0].extra["kind"] == "news"


def test_filters_out_non_english_by_default():
    titles = [i.title for i in _connector(_ok).fetch("q").items]
    assert "Заголовок на русском" not in titles


def test_english_only_false_keeps_all_languages():
    items = _connector(_ok, english_only=False).fetch("q").items
    assert len(items) == 3  # the Russian article is kept


def test_max_results_caps_output():
    items = _connector(_ok, max_results=1).fetch("q").items
    assert len(items) == 1


def test_blank_query_returns_no_items():
    # No network call needed for a blank query.
    def handler(_request):
        raise AssertionError("should not be called for a blank query")

    assert _connector(handler).fetch("   ").items == []


def test_rate_limit_429_returns_no_items():
    items = _connector(lambda r: httpx.Response(429, text="rate limited")).fetch("q").items
    assert items == []  # GDELT throttling degrades to empty, never raises


def test_malformed_json_returns_no_items():
    items = _connector(lambda r: httpx.Response(200, text="not json")).fetch("q").items
    assert items == []


def test_transport_error_returns_no_items():
    def boom(_request):
        raise httpx.ConnectError("no route")

    assert _connector(boom).fetch("q").items == []


def test_sends_expected_query_params():
    captured = {}

    def handler(request):
        captured.update(dict(request.url.params))
        return httpx.Response(200, json={"articles": []})

    _connector(handler, timespan="1week").fetch("latest news on ukraine")
    assert captured["query"] == "ukraine"  # filler stripped to the salient subject
    assert captured["mode"] == "artlist" and captured["format"] == "json"
    assert captured["sort"] == "datedesc" and captured["timespan"] == "1week"


def test_broad_question_uses_broad_world_query():
    captured = {}

    def handler(request):
        captured.update(dict(request.url.params))
        return httpx.Response(200, json={"articles": []})

    _connector(handler).fetch("what is going on around the world right now?")
    assert "world" in captured["query"].lower()  # the broad fallback, not the raw question


def test_name_and_description():
    connector = GdeltConnector()
    assert connector.name == "gdelt"
    assert "global" in connector.description.lower()
