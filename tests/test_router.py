"""Router: LLM (format=json) -> validated connector names; unknown/garbage -> []."""

from jarvis.connectors.base import Connector
from jarvis.knowledge.router import Router


class _FakeLLM:
    def __init__(self, reply):
        self.reply = reply
        self.last_format = None
        self.last_think = None

    def generate(self, prompt, *, format=None, think=None):
        self.last_format = format
        self.last_think = think
        return self.reply


class _StubConnector(Connector):
    def __init__(self, name):
        self.name = name
        self.description = f"{name} source"

    def fetch(self, query):  # the router never fetches
        raise NotImplementedError


def _router(reply, names=("hn", "markets")):
    return Router(_FakeLLM(reply), [_StubConnector(n) for n in names])


def test_route_parses_connector_names():
    assert _router('{"connectors": ["hn"]}').route("what's on hn") == ["hn"]


def test_route_filters_unknown_names():
    assert _router('{"connectors": ["hn", "weather"]}').route("q") == ["hn"]


def test_route_empty_on_no_match():
    assert _router('{"connectors": []}').route("hello") == []


def test_route_empty_on_garbage():
    assert _router("not json at all").route("q") == []


def test_route_requests_a_schema_and_disables_thinking():
    llm = _FakeLLM('{"connectors": []}')
    Router(llm, [_StubConnector("hn")]).route("q")
    assert isinstance(llm.last_format, dict)  # a JSON schema, not plain "json"
    assert llm.last_format["required"] == ["connectors"]
    assert llm.last_think is False
