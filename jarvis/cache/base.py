"""Cache seam: a TTL key-value cache for connector responses.

SQLite is the Phase 1 backend; the interface keeps it swappable (Redis later, per the architecture's
always-on/multi-process phase). ``get`` returns a value only while fresh; expired or missing keys
return ``None``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Cache(ABC):
    @abstractmethod
    def get(self, key: str) -> str | None:
        """Return the cached value for ``key`` if present and not expired, else ``None``."""

    @abstractmethod
    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Store ``value`` under ``key``, expiring ``ttl_seconds`` from now."""
