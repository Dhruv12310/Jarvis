"""Phase 0 self-test: an offline logic check with fakes, plus a live integration check.

The integration test runs the real stack against Ollama and is skipped when Ollama is unreachable.
"""

import pytest

from jarvis.selftest import run_selftest


class _FakeLLM:
    def __init__(self, reply: str = "hello from a fake model") -> None:
        self._reply = reply

    def generate(self, prompt: str) -> str:
        return self._reply


def _ollama_reachable() -> bool:
    try:
        from ollama import Client

        from jarvis.config import config

        Client(host=config.ollama_host).list()
        return True
    except Exception:
        return False


def test_selftest_passes_with_fakes(fake_embedder):
    result = run_selftest(llm=_FakeLLM(), embedder=fake_embedder)

    assert result.passed, str(result)


def test_selftest_fails_when_model_returns_empty(fake_embedder):
    result = run_selftest(llm=_FakeLLM(reply="   "), embedder=fake_embedder)

    assert not result.passed
    assert "empty response" in str(result)


@pytest.mark.integration
def test_phase0_selftest_passes_live():
    if not _ollama_reachable():
        pytest.skip("Ollama not reachable")

    result = run_selftest()

    assert result.passed, str(result)
