"""ModelRouter: the Tier-2 cloud seam. Offline (a fake Anthropic client; no SDK, no network)."""

import pytest

from jarvis.router.model_router import CloudUnavailable, ModelRouter, _text_of


class _Block:
    def __init__(self, text):
        self.text = text


class _Message:
    def __init__(self, text):
        self.content = [_Block(text)]


class _FakeAnthropic:
    """Captures the outbound request so a test can assert what actually crossed the boundary."""

    def __init__(self, reply="REPORT"):
        self.reply = reply
        self.captured: dict | None = None
        self.messages = self  # the SDK shape is client.messages.create(...)

    def create(self, **kwargs):
        self.captured = kwargs
        return _Message(self.reply)


def test_unavailable_without_key_or_client():
    router = ModelRouter(api_key="", client=None)
    assert router.available is False
    with pytest.raises(CloudUnavailable):
        router.deepdive("data", "instruction")


def test_available_with_injected_client_and_returns_text():
    fake = _FakeAnthropic(reply="deep dive text")
    router = ModelRouter(api_key="", model="claude-test", client=fake)
    assert router.available is True

    out = router.deepdive("Company: Apple", "Analyze this")

    assert out == "deep dive text"
    assert fake.captured["model"] == "claude-test"
    assert "Analyze this" in fake.captured["messages"][0]["content"]
    assert "Company: Apple" in fake.captured["messages"][0]["content"]


def test_redacts_before_sending():
    # Defense in depth: even if a caller leaks a secret into the block, it must be scrubbed before
    # the request crosses to the cloud.
    fake = _FakeAnthropic()
    router = ModelRouter(api_key="k", client=fake)

    router.deepdive("see https://x?token=SECRET123 and key apikey=ABCDEF", "go")

    sent = fake.captured["messages"][0]["content"]
    assert "SECRET123" not in sent and "ABCDEF" not in sent
    assert "token=***" in sent and "apikey=***" in sent


def test_available_when_only_key_set():
    # A real key (no injected client) reports available without building the SDK client.
    assert ModelRouter(api_key="sk-ant-xyz", client=None).available is True


def test_text_of_joins_blocks_and_ignores_empty():
    class M:
        content = [_Block("a"), _Block(""), _Block("b")]

    assert _text_of(M()) == "a\nb"
    assert _text_of(object()) == ""  # no content attribute -> empty, never raises
