"""Vector store seam: similarity retrieval over embeddings.

``metadata`` is optional now so later Core fields (type, importance, tier) can ride along without an
interface change. Phase 0 does not build MemoryRecord; it just keeps the signature open.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class VectorHit:
    id: str
    text: str
    distance: float  # backend distance, lower is closer (not a higher-is-better score)
    metadata: dict | None = None


class VectorStore(ABC):
    @abstractmethod
    def add(
        self, id: str, text: str, embedding: Sequence[float], metadata: dict | None = None
    ) -> None:
        """Store an embedding with its source text and optional metadata under ``id``."""

    @abstractmethod
    def query(self, embedding: Sequence[float], k: int = 5) -> list[VectorHit]:
        """Return the ``k`` nearest stored items to ``embedding``, closest first."""

    @abstractmethod
    def upsert(
        self, id: str, text: str, embedding: Sequence[float], metadata: dict | None = None
    ) -> None:
        """Add or replace the item under ``id`` (used to refresh a memory, e.g. last_accessed)."""

    @abstractmethod
    def list_all(self, limit: int = 50) -> list[VectorHit]:
        """Return up to ``limit`` stored items (unordered, no distance) for enumeration."""
