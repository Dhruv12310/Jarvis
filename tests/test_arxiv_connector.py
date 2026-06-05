"""ArxivConnector: arXiv Atom feed -> paper Items. Offline (keyless API mocked); never raises."""

import httpx

from jarvis.connectors.arxiv import ArxivConnector, _byline

_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2405.12345v2</id>
    <published>2026-05-30T17:00:00Z</published>
    <title>Deep Learning for
       Personal Finance</title>
    <summary>   We study budgeting models.   </summary>
    <author><name>Jane Smith</name></author>
    <author><name>Bob Lee</name></author>
    <link href="http://arxiv.org/abs/2405.12345v2" rel="alternate"/>
    <link title="pdf" href="http://arxiv.org/pdf/2405.12345v2" rel="related"/>
    <arxiv:primary_category term="cs.LG"/>
    <category term="cs.LG"/>
    <category term="q-fin.GN"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2405.99999v1</id>
    <published>2026-05-29T00:00:00Z</published>
    <title>Solo Paper</title>
    <summary>One author.</summary>
    <author><name>Ada Solo</name></author>
    <link href="http://arxiv.org/abs/2405.99999v1" rel="alternate" type="text/html"/>
  </entry>
</feed>"""


def _connector(handler, max_results=10):
    return ArxivConnector(
        client=httpx.Client(transport=httpx.MockTransport(handler)), max_results=max_results
    )


def _ok(_request):
    return httpx.Response(200, content=_FEED)


def test_parses_entries_into_paper_items():
    items = _connector(_ok).fetch("personal finance").items
    paper = items[0]

    assert paper.title == "Deep Learning for Personal Finance"  # whitespace normalized
    assert paper.detail == "Jane Smith et al., 2026-05-30"
    assert paper.url == "http://arxiv.org/abs/2405.12345"  # version stripped (v2 -> none)
    assert paper.extra["kind"] == "paper"
    assert paper.extra["authors"] == ["Jane Smith", "Bob Lee"]
    assert paper.extra["abstract"] == "We study budgeting models."  # stripped
    assert paper.extra["primary_category"] == "cs.LG"
    assert paper.extra["categories"] == ["cs.LG", "q-fin.GN"]
    assert paper.extra["pdf_url"] == "http://arxiv.org/pdf/2405.12345v2"
    assert paper.extra["arxiv_id"] == "http://arxiv.org/abs/2405.12345"


def test_single_author_byline_has_no_et_al():
    items = _connector(_ok).fetch("q").items
    assert items[1].detail == "Ada Solo, 2026-05-29"


def test_sends_sort_and_search_params():
    captured = {}

    def handler(request):
        captured.update(dict(request.url.params))
        return httpx.Response(200, content=_FEED)

    _connector(handler, max_results=7).fetch("llm agents")
    assert captured["search_query"] == "all:llm agents"
    assert captured["sortBy"] == "submittedDate" and captured["sortOrder"] == "descending"
    assert captured["max_results"] == "7"


def test_blank_query_makes_no_call():
    def handler(_request):
        raise AssertionError("no request for a blank query")

    assert _connector(handler).fetch("   ").items == []


def test_non_200_returns_no_items():
    assert _connector(lambda r: httpx.Response(429, text="slow down")).fetch("q").items == []


def test_transport_error_returns_no_items():
    def boom(_request):
        raise httpx.ConnectError("no route")

    assert _connector(boom).fetch("q").items == []


def test_malformed_xml_returns_no_items():
    assert _connector(lambda r: httpx.Response(200, content=b"not xml <<<")).fetch("q").items == []


def test_name_and_description():
    connector = ArxivConnector()
    assert connector.name == "arxiv"
    assert "research" in connector.description.lower()


def test_byline_helper_edges():
    assert _byline([], "") == ""
    assert _byline(["Solo One"], "2026-01-02T00:00:00Z") == "Solo One, 2026-01-02"
    assert _byline(["A", "B", "C"], "") == "A et al."
