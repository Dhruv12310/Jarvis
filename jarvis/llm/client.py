"""LLM client seam: a prompt goes in, a text response comes out.

The interface is a structural ``Protocol`` so the orchestrator depends on the seam, not on Ollama.
``OllamaClient`` is the Phase 0 implementation: a thin wrapper over the local Ollama generate
endpoint. No tools, no routing, no cloud.
"""

from __future__ import annotations

from typing import Protocol

from ollama import Client

from jarvis.config import config


class LLMClient(Protocol):
    """Anything that turns a prompt into a text completion.

    ``format`` is optional and backward compatible: ``None`` is free text; a JSON-schema ``dict``
    constrains the model to that exact structure (used by the Phase 1 router, since plain ``"json"``
    lets a thinking model collapse to ``{}``). ``think`` toggles a reasoning model's thinking
    (``False`` for the mechanical router; default for prose). Phase 0 callers pass nothing.
    """

    def generate(
        self, prompt: str, *, format: str | dict | None = None, think: bool | None = None
    ) -> str: ...


class OllamaClient:
    """Generate text with a local Ollama model. The model and host come from config by default."""

    def __init__(self, model: str | None = None, host: str | None = None) -> None:
        self._model = model or config.llm_model
        self._client = Client(host=host or config.ollama_host)

    def generate(
        self, prompt: str, *, format: str | dict | None = None, think: bool | None = None
    ) -> str:
        response = self._client.generate(
            model=self._model, prompt=prompt, format=format, think=think
        )
        return response.response
