"""Offline unit tests for the Ollama wrappers: default resolution and response unwrapping.

These close the gap where OllamaClient/OllamaEmbedder were exercised only by the live integration
test: a fake ollama Client lets the unwrap logic and config-default resolution be tested offline.
"""

from types import SimpleNamespace

from jarvis.llm.client import OllamaClient
from jarvis.llm.embedder import OllamaEmbedder


class _FakeOllama:
    """Stands in for ollama.Client; records the host and the most recent call arguments."""

    def __init__(self, host=None):
        self.host = host
        self.generate_args = None
        self.format_arg = None
        self.think_arg = None
        self.embed_args = None

    def generate(self, model, prompt, format=None, think=None):
        self.generate_args = (model, prompt)
        self.format_arg = format
        self.think_arg = think
        return SimpleNamespace(response="stub reply")

    def embed(self, model, input):
        self.embed_args = (model, input)
        return SimpleNamespace(embeddings=[[0.1, 0.2, 0.3]])


def test_ollama_client_unwraps_response_and_uses_config_defaults(monkeypatch):
    created = {}

    def factory(host=None):
        created["client"] = _FakeOllama(host)
        return created["client"]

    monkeypatch.setattr("jarvis.llm.client.Client", factory)

    reply = OllamaClient().generate("hi")

    assert reply == "stub reply"
    assert created["client"].host == "http://localhost:11434"  # config default host
    assert created["client"].generate_args == ("qwen3:14b", "hi")  # config default model


def test_ollama_client_explicit_model_and_host_override_config(monkeypatch):
    created = {}
    monkeypatch.setattr(
        "jarvis.llm.client.Client",
        lambda host=None: created.setdefault("client", _FakeOllama(host)),
    )

    OllamaClient(model="phi4", host="http://elsewhere:11434").generate("x")

    assert created["client"].host == "http://elsewhere:11434"
    assert created["client"].generate_args[0] == "phi4"


def test_ollama_embedder_returns_first_embedding_as_list(monkeypatch):
    monkeypatch.setattr("jarvis.llm.embedder.Client", lambda host=None: _FakeOllama(host))

    vector = OllamaEmbedder().embed("hello")

    assert vector == [0.1, 0.2, 0.3]
    assert isinstance(vector, list)


def test_ollama_client_forwards_format(monkeypatch):
    created = {}
    monkeypatch.setattr(
        "jarvis.llm.client.Client",
        lambda host=None: created.setdefault("client", _FakeOllama(host)),
    )

    OllamaClient().generate("give me json", format="json")

    assert created["client"].format_arg == "json"


def test_ollama_client_forwards_think(monkeypatch):
    created = {}
    monkeypatch.setattr(
        "jarvis.llm.client.Client",
        lambda host=None: created.setdefault("client", _FakeOllama(host)),
    )

    OllamaClient().generate("q", think=False)

    assert created["client"].think_arg is False
