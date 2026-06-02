"""MemoryRecord: the core memory object (Core spec §5.1).

Episodic + semantic memory. The embedding is not carried here - it lives in the vector store,
computed from ``content`` by the embedder. This dataclass is the logical record (content + fields).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class MemoryRecord:
    id: str
    type: str  # observation|preference|decision|pattern|outcome|reflection
    content: str
    created_at: datetime
    last_accessed_at: datetime  # bumped on retrieval; drives recency
    importance: float  # [0..1], heuristic at write time (Phase 2)
    tier: str  # foundational|tactical|observational
    confidence: float  # [0..1]
    source: str  # interaction|collector|reflection|feedback
    links: list[str] = field(default_factory=list)  # related record ids
    metadata: dict = field(default_factory=dict)
