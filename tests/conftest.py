"""Shared test fixtures."""

import hashlib

import pytest


class FakeEmbedder:
    """Deterministic, offline embedder: SHA1 bag-of-words into a fixed-dim vector.

    Identical text yields identical vectors (distance 0); different text yields different vectors.
    No live model and no dependence on the process hash seed, so similarity assertions are stable.
    """

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in text.lower().split():
            bucket = int.from_bytes(hashlib.sha1(token.encode()).digest()[:4], "big") % self.dim
            vec[bucket] += 1.0
        return vec


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()
