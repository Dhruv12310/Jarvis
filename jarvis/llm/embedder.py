"""Embedding seam: text to vector, via a local Ollama model.

Structural Protocol so the vector store depends on the seam, not on Ollama. OllamaEmbedder is the
Phase 0 implementation using the local embed endpoint.
"""

from __future__ import annotations

from typing import Protocol

from ollama import Client

from jarvis.config import config


class Embedder(Protocol):
    """Anything that turns text into a fixed-length embedding vector."""

    def embed(self, text: str) -> list[float]: ...


class OllamaEmbedder:
    """Embed text with a local Ollama model. The model and host come from config by default."""

    def __init__(self, model: str | None = None, host: str | None = None) -> None:
        self._model = model or config.embed_model
        self._client = Client(host=host or config.ollama_host)

    def embed(self, text: str) -> list[float]:
        response = self._client.embed(model=self._model, input=text)
        return list(response.embeddings[0])
