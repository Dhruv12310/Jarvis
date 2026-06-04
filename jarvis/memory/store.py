"""MemoryStore: save typed MemoryRecords and retrieve them by the Core §7.1 score.

Stage 2 (store) + Stage 3 (retrieve). Retrieval is DETERMINISTIC: recency + importance + relevance,
each min-max normalized over the candidate set, weighted, top-K. The LLM is not involved. The
embedding lives in the (cosine) vector store; the record's scalar fields ride in the metadata.
"""

from __future__ import annotations

import json
import math
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from jarvis.config import config
from jarvis.llm.embedder import Embedder
from jarvis.memory.record import MemoryRecord
from jarvis.stores.vector import VectorHit, VectorStore


def default_importance(content: str, *, explicit: bool = False) -> float:
    """Phase 2 heuristic (Core §11 allows heuristic-first); a classifier/LLM refines it later."""
    score = 0.7 if explicit else 0.5
    if len(content) > 200:
        score = min(1.0, score + 0.1)
    return score


class MemoryStore:
    def __init__(self, vector: VectorStore, embedder: Embedder) -> None:
        self._vector = vector
        self._embedder = embedder

    def save(self, record: MemoryRecord) -> None:
        self._vector.upsert(
            id=record.id,
            text=record.content,
            embedding=self._embedder.embed(record.content),
            metadata=_to_metadata(record),
        )

    def remember(self, content: str, *, explicit: bool = False) -> MemoryRecord:
        """Build and persist an explicit Phase 2 memory (a stamped observation)."""
        now = datetime.now(UTC)
        record = MemoryRecord(
            id=uuid4().hex,
            type="observation",
            content=content,
            created_at=now,
            last_accessed_at=now,
            importance=default_importance(content, explicit=explicit),
            tier="observational",
            confidence=0.6,
            source="interaction",
        )
        self.save(record)
        return record

    def all(self, limit: int = 50) -> list[MemoryRecord]:
        """Enumerate stored memories (unordered) for inspection; not a ranked retrieval."""
        return [_to_record(hit) for hit in self._vector.list_all(limit=limit)]

    def forget(self, memory_id: str) -> None:
        """Delete a memory by id (the user controls their own model)."""
        self._vector.delete(memory_id)

    def retrieve(self, query: str, k: int = 5) -> list[MemoryRecord]:
        hits = self._vector.query(self._embedder.embed(query), k=config.memory_candidate_pool)
        if not hits:
            return []
        now = datetime.now(UTC)
        recency = _norm([_recency(_last_accessed(h), now) for h in hits])
        importance = _norm([float((h.metadata or {}).get("importance", 0.0)) for h in hits])
        relevance = _norm(
            [1.0 - h.distance for h in hits]
        )  # 1 - cosine distance = cosine similarity
        ranked = sorted(
            zip(hits, recency, importance, relevance, strict=False),
            key=lambda t: (
                config.memory_w_rec * t[1] + config.memory_w_imp * t[2] + config.memory_w_rel * t[3]
            ),
            reverse=True,
        )
        results = []
        for hit, *_ in ranked[:k]:
            record = replace(_to_record(hit), last_accessed_at=now)  # bump on retrieval
            # Metadata-only update: refresh last_accessed_at without re-embedding the content.
            self._vector.update_metadata(record.id, _to_metadata(record))
            results.append(record)
        return results


def _recency(last_accessed: datetime, now: datetime) -> float:
    hours = max(0.0, (now - last_accessed).total_seconds() / 3600.0)
    return math.exp(-config.memory_recency_lambda * hours)


def _norm(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi <= lo:
        return [0.0 for _ in values]  # no signal when all equal
    return [(v - lo) / (hi - lo) for v in values]


def _last_accessed(hit: VectorHit) -> datetime:
    return datetime.fromisoformat((hit.metadata or {})["last_accessed_at"])


def _to_metadata(record: MemoryRecord) -> dict:
    # Chroma metadata is flat scalars; lists/dicts are JSON-encoded.
    return {
        "type": record.type,
        "created_at": record.created_at.isoformat(),
        "last_accessed_at": record.last_accessed_at.isoformat(),
        "importance": record.importance,
        "tier": record.tier,
        "confidence": record.confidence,
        "source": record.source,
        "links": json.dumps(record.links),
        "extra": json.dumps(record.metadata),
    }


def _to_record(hit: VectorHit) -> MemoryRecord:
    m = hit.metadata or {}
    return MemoryRecord(
        id=hit.id,
        type=m["type"],
        content=hit.text,
        created_at=datetime.fromisoformat(m["created_at"]),
        last_accessed_at=datetime.fromisoformat(m["last_accessed_at"]),
        importance=float(m["importance"]),
        tier=m["tier"],
        confidence=float(m["confidence"]),
        source=m["source"],
        links=json.loads(m.get("links", "[]")),
        metadata=json.loads(m.get("extra", "{}")),
    )
