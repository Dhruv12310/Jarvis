"""Knowledge pipeline: route -> fetch -> answer; None on no-match; cached flag; error contained."""

from jarvis.connectors.base import Connector, ConnectorResult, Item, Source
from jarvis.knowledge.pipeline import Knowledge


class _FakeRouter:
    def __init__(self, names):
        self.names = names

    def route(self, question):
        return self.names


class _FakeConnector(Connector):
    def __init__(self, name, *, hit=False):
        self.name = name
        self.description = "d"
        self._hit = hit
        self.calls = 0

    @property
    def last_was_cache_hit(self):
        return self._hit

    def fetch(self, query):
        self.calls += 1
        return ConnectorResult(Source(self.name), [Item("t", "d")], query)


class _FakeAnswerer:
    def answer(self, question, results):
        return f"answer:{len(results)}"


def test_ask_routes_fetches_and_answers():
    conn = _FakeConnector("hn")
    knowledge = Knowledge(_FakeRouter(["hn"]), {"hn": conn}, _FakeAnswerer())

    ans = knowledge.ask("q")

    assert ans.text == "answer:1"
    assert conn.calls == 1


def test_ask_returns_none_when_no_connector():
    knowledge = Knowledge(_FakeRouter([]), {"hn": _FakeConnector("hn")}, _FakeAnswerer())
    assert knowledge.ask("hello") is None


def test_ask_marks_cached_when_all_from_cache():
    knowledge = Knowledge(
        _FakeRouter(["hn"]), {"hn": _FakeConnector("hn", hit=True)}, _FakeAnswerer()
    )
    assert knowledge.ask("q").cached is True


def test_ask_not_cached_when_fresh():
    knowledge = Knowledge(_FakeRouter(["hn"]), {"hn": _FakeConnector("hn")}, _FakeAnswerer())
    assert knowledge.ask("q").cached is False


def test_ask_survives_a_connector_error():
    class _Boom(_FakeConnector):
        def fetch(self, query):
            raise RuntimeError("source down")

    knowledge = Knowledge(_FakeRouter(["hn"]), {"hn": _Boom("hn")}, _FakeAnswerer())

    ans = knowledge.ask("q")  # must not crash

    assert ans.text == "answer:0"  # the failing source is treated as empty


def test_ask_fetches_every_selected_connector():
    hn = _FakeConnector("hn")
    markets = _FakeConnector("markets")
    knowledge = Knowledge(
        _FakeRouter(["hn", "markets"]), {"hn": hn, "markets": markets}, _FakeAnswerer()
    )

    ans = knowledge.ask("q")

    assert hn.calls == 1
    assert markets.calls == 1
    assert ans.text == "answer:2"  # both results reach the answerer


def test_real_connector_http_error_is_contained():
    import httpx

    from jarvis.connectors.hn import HackerNewsConnector

    transport = httpx.MockTransport(lambda r: httpx.Response(500, json={}))
    hn = HackerNewsConnector(client=httpx.Client(transport=transport))
    knowledge = Knowledge(_FakeRouter(["hn"]), {"hn": hn}, _FakeAnswerer())

    ans = knowledge.ask("q")  # HN raises HTTPStatusError -> pipeline contains it -> empty results

    assert ans.text == "answer:0"
