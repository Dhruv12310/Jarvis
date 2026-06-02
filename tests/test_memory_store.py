"""MemoryStore: typed MemoryRecord round-trip + deterministic §7.1 retrieval.

A fake vector store (cosine via a real cosine over the deterministic fake embedder) lets each §7.1
term (recency, importance, relevance) be isolated by holding the others equal.
"""

import math
from datetime import UTC, datetime, timedelta

from jarvis.memory.record import MemoryRecord
from jarvis.memory.store import MemoryStore, default_importance
from jarvis.stores.vector import VectorHit, VectorStore


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


class _FakeVector(VectorStore):
    def __init__(self):
        self.store = {}  # id -> (text, embedding, metadata)

    def add(self, id, text, embedding, metadata=None):
        self.store[id] = (text, list(embedding), metadata or {})

    def upsert(self, id, text, embedding, metadata=None):
        self.store[id] = (text, list(embedding), metadata or {})

    def query(self, embedding, k=5):
        hits = [
            VectorHit(id=i, text=t, distance=1.0 - _cosine(embedding, e), metadata=m)
            for i, (t, e, m) in self.store.items()
        ]
        hits.sort(key=lambda h: h.distance)
        return hits[:k]

    def list_all(self, limit=50):
        return [
            VectorHit(id=i, text=t, distance=0.0, metadata=m)
            for i, (t, _e, m) in list(self.store.items())[:limit]
        ]


def _record(rec_id, content, *, importance=0.5, last_accessed=None):
    now = datetime.now(UTC)
    return MemoryRecord(
        id=rec_id,
        type="observation",
        content=content,
        created_at=now,
        last_accessed_at=last_accessed or now,
        importance=importance,
        tier="observational",
        confidence=1.0,
        source="interaction",
        links=[],
        metadata={},
    )


def _memory(fake_embedder):
    return MemoryStore(_FakeVector(), fake_embedder)


def test_save_and_retrieve_round_trips_a_record(fake_embedder):
    memory = _memory(fake_embedder)
    memory.save(_record("1", "the dentist appointment is friday", importance=0.6))

    results = memory.retrieve("dentist appointment friday", k=1)

    assert len(results) == 1
    r = results[0]
    assert r.id == "1"
    assert r.type == "observation"
    assert r.content == "the dentist appointment is friday"
    assert r.importance == 0.6
    assert r.tier == "observational"


def test_importance_breaks_ties_on_equal_relevance(fake_embedder):
    memory = _memory(fake_embedder)
    memory.save(_record("low", "alpha", importance=0.1))
    memory.save(_record("high", "alpha", importance=0.9))

    assert memory.retrieve("alpha", k=2)[0].id == "high"


def test_recency_breaks_ties_on_equal_relevance_and_importance(fake_embedder):
    memory = _memory(fake_embedder)
    memory.save(_record("old", "alpha", last_accessed=datetime.now(UTC) - timedelta(hours=500)))
    memory.save(_record("new", "alpha"))

    assert memory.retrieve("alpha", k=2)[0].id == "new"


def test_relevance_ranks_closer_content_first(fake_embedder):
    memory = _memory(fake_embedder)
    memory.save(_record("a", "alpha apple orchard"))
    memory.save(_record("b", "beta banana boat"))

    assert memory.retrieve("alpha apple orchard", k=2)[0].id == "a"


def test_retrieve_bumps_last_accessed(fake_embedder):
    memory = _memory(fake_embedder)
    old = datetime.now(UTC) - timedelta(days=30)
    memory.save(_record("1", "alpha", last_accessed=old))

    memory.retrieve("alpha", k=1)

    stored_meta = memory._vector.store["1"][2]
    assert datetime.fromisoformat(stored_meta["last_accessed_at"]) > old


def test_empty_store_returns_nothing(fake_embedder):
    assert _memory(fake_embedder).retrieve("anything", k=5) == []


def test_default_importance_heuristic():
    assert default_importance("short") == 0.5
    assert default_importance("short", explicit=True) == 0.7
    assert default_importance("x" * 300) > 0.5
