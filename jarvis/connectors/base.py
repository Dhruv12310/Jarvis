"""Connector seam: each connector fetches normalized public data for a query.

Connectors are independent: a connector imports only this module plus stdlib/httpx, never
another connector. Outbound HTTP lives only in connector implementations (the trust boundary:
only Collectors cross out, to public APIs). Results are plain value objects so the router and
answerer treat every source identically, and so they serialize cleanly into the cache.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Source:
    name: str
    url: str | None = None


@dataclass(frozen=True)
class Item:
    title: str
    detail: str  # one-line human-readable fact (e.g. "NVDA +2.3% to $X")
    url: str | None = None
    extra: dict | None = None  # connector-specific structured fields (e.g. {"change_pct": 2.3})


@dataclass(frozen=True)
class ConnectorResult:
    source: Source
    items: list[Item]
    query: str


class Connector(ABC):
    name: str  # stable id used by the router: "hn" | "markets" | "news"
    description: str  # what it covers; shown to the router LLM to decide relevance

    @abstractmethod
    def fetch(self, query: str) -> ConnectorResult: ...


def serialize_result(result: ConnectorResult) -> str:
    """JSON for the cache. Deterministic; connectors never put secrets in results."""
    return json.dumps(asdict(result))


def deserialize_result(raw: str) -> ConnectorResult:
    data = json.loads(raw)
    return ConnectorResult(
        source=Source(**data["source"]),
        items=[Item(**item) for item in data["items"]],
        query=data["query"],
    )
