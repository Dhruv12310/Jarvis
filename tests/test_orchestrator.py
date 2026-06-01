"""The Phase 0 orchestrator is a thin pass-through to the LLM client: text in, text out.

No network here: a FakeLLMClient stands in for Ollama so the test stays a fast unit test.
"""

from jarvis.orchestrator import Orchestrator


class FakeLLMClient:
    """Records the last prompt and returns a canned, identifiable reply."""

    def __init__(self, reply: str = "pong") -> None:
        self.reply = reply
        self.last_prompt: str | None = None

    def generate(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self.reply


def test_chat_returns_the_llm_response():
    orchestrator = Orchestrator(FakeLLMClient(reply="hello there"))
    assert orchestrator.chat("hi") == "hello there"


def test_chat_passes_the_prompt_through_unchanged():
    fake = FakeLLMClient()
    orchestrator = Orchestrator(fake)

    orchestrator.chat("remember this exact text")

    assert fake.last_prompt == "remember this exact text"


def test_chat_only_delegates_no_transform():
    # Phase 0: no routing, no tools, no rewriting. Whatever the client returns is returned verbatim.
    fake = FakeLLMClient(reply="  spaced  ")
    orchestrator = Orchestrator(fake)
    assert orchestrator.chat("anything") == "  spaced  "
