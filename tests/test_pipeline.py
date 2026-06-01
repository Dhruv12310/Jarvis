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
