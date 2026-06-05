"""NewsConnector: GNews articles -> Items. Offline via MockTransport; covers no-key and 403."""

import httpx

from jarvis.connectors.news import NewsConnector

_FIXTURE = {
    "totalArticles": 2,
    "articles": [
        {
            "title": "AI breakthrough announced",
            "description": "desc one",
            "url": "https://news.test/1",
            "publishedAt": "2026-06-01T08:00:00Z",
            "source": {"name": "TechWire", "url": "https://tw.test"},
        },
        {
            "title": "Markets rally",
            "description": "desc two",
            "url": "https://news.test/2",
            "publishedAt": "2026-05-31T10:00:00Z",
            "source": {"name": "BizDaily", "url": "https://bd.test"},
        },
    ],
}


def _connector(handler, api_key="testkey"):
    transport = httpx.MockTransport(handler)
    return NewsConnector(client=httpx.Client(transport=transport), api_key=api_key)


def test_fetch_normalizes_articles_to_items():
    def handler(request):
        assert request.url.path == "/api/v4/search"
        assert request.url.params.get("q") == "AI"
        assert request.url.params.get("apikey")
        return httpx.Response(200, json=_FIXTURE)

    result = _connector(handler).fetch("AI")

    assert result.source.name == "GNews"
    assert [i.title for i in result.items] == ["AI breakthrough announced", "Markets rally"]
    assert result.items[0].detail == "TechWire, 2026-06-01"
    assert result.items[0].url == "https://news.test/1"
    assert result.items[0].extra["source"] == "TechWire"


def test_broad_question_falls_back_to_top_headlines():
    # A conversational question with no specific subject -> /top-headlines, not a doomed /search.
    def handler(request):
        assert request.url.path == "/api/v4/top-headlines"
        assert "q" not in request.url.params  # no search term on the headlines call
        assert request.url.params.get("category") == "world"
        return httpx.Response(200, json=_FIXTURE)

    items = _connector(handler).fetch("what is going on in the world right now?").items
    assert [i.title for i in items] == ["AI breakthrough announced", "Markets rally"]


def test_specific_subject_uses_search_with_keywords():
    def handler(request):
        assert request.url.path == "/api/v4/search"
        assert request.url.params.get("q") == "Ukraine"  # stopwords/filler stripped
        return httpx.Response(200, json=_FIXTURE)

    assert _connector(handler).fetch("latest news on Ukraine").items  # non-empty


def test_no_key_returns_no_items():
    result = _connector(lambda r: httpx.Response(200, json=_FIXTURE), api_key="").fetch("AI")
    assert result.items == []


def test_error_response_returns_no_items():
    # e.g. a 403 from an unactivated GNews account -> no items, never invented headlines
    result = _connector(lambda r: httpx.Response(403, json={"errors": ["activate"]})).fetch("AI")
    assert result.items == []


def test_name_and_description():
    connector = _connector(lambda r: httpx.Response(200, json={"articles": []}))
    assert connector.name == "news"
    assert "news" in connector.description.lower()


def test_missing_articles_key_yields_no_items():
    result = _connector(lambda r: httpx.Response(200, json={"totalArticles": 0})).fetch("AI")
    assert result.items == []
