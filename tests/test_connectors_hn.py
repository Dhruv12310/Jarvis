"""HackerNewsConnector: normalizes Algolia HN Search hits into Items. Offline via MockTransport."""

import httpx

from jarvis.connectors.hn import HackerNewsConnector

_FIXTURE = {
    "hits": [
        {
            "title": "A cool AI thing",
            "url": "https://example.com/ai",
            "points": 120,
            "num_comments": 45,
            "author": "alice",
            "objectID": "111",
            "created_at": "2026-01-01T00:00:00Z",
        },
        {
            "title": "Ask HN: a text post",
            "url": None,
            "points": 10,
            "num_comments": 3,
            "author": "bob",
            "objectID": "222",
            "created_at": "2026-01-02T00:00:00Z",
        },
    ]
}


def _connector(handler):
    return HackerNewsConnector(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_fetch_normalizes_hits_to_items():
    def handler(request):
        assert request.url.path == "/api/v1/search"
        assert request.url.params.get("query") == "rust"
        assert request.url.params.get("tags") == "story"
        return httpx.Response(200, json=_FIXTURE)

    result = _connector(handler).fetch("rust")

    assert result.source.name == "Hacker News (Algolia)"
    assert [i.title for i in result.items] == ["A cool AI thing", "Ask HN: a text post"]
    assert result.items[0].detail == "120 points, 45 comments"
    assert result.items[0].url == "https://example.com/ai"
    assert result.items[0].extra["points"] == 120


def test_text_post_without_url_falls_back_to_hn_item():
    result = _connector(lambda r: httpx.Response(200, json=_FIXTURE)).fetch("anything")
    assert result.items[1].url == "https://news.ycombinator.com/item?id=222"


def test_empty_hits_yields_no_items():
    result = _connector(lambda r: httpx.Response(200, json={"hits": []})).fetch("zzz")
    assert result.items == []


def test_name_and_description():
    connector = _connector(lambda r: httpx.Response(200, json={"hits": []}))
    assert connector.name == "hn"
    assert "startup" in connector.description.lower()
