"""Chroma implementation of VectorStore (bring-your-own-embeddings).

This is the ONLY module that imports chromadb. The collection is created with no embedding_function
and every add/query passes embeddings explicitly, so Chroma never runs a built-in embedder (no model
download). Telemetry is disabled to honor the local-first trust boundary.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import chromadb
from chromadb.config import Settings

from jarvis.stores.vector import VectorHit, VectorStore

_COLLECTION = "notes"


class ChromaVectorStore(VectorStore):
    def __init__(self, vector_dir: Path | str, collection: str = _COLLECTION) -> None:
        self._client = chromadb.PersistentClient(
            path=str(vector_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        # No embedding_function: we always supply embeddings ourselves.
        self._collection = self._client.get_or_create_collection(name=collection)

    def add(
        self, id: str, text: str, embedding: Sequence[float], metadata: dict | None = None
    ) -> None:
        self._collection.add(
            ids=[id],
            embeddings=[list(embedding)],
            documents=[text],
            metadatas=[metadata] if metadata else None,
        )

    def query(self, embedding: Sequence[float], k: int = 5) -> list[VectorHit]:
        result = self._collection.query(query_embeddings=[list(embedding)], n_results=k)
        return self._to_hits(result)

    @staticmethod
    def _to_hits(result) -> list[VectorHit]:
        # Chroma nests one inner list per query; we send a single query, so take [0] of each.
        ids = result["ids"][0]
        documents = result["documents"][0]
        distances = result["distances"][0]
        # metadatas is absent/None when nothing was stored; fall back to one None per hit.
        metadatas_for_query = (result.get("metadatas") or [None])[0]
        metadatas = metadatas_for_query or [None] * len(ids)
        return [
            VectorHit(id=hit_id, text=text, distance=float(distance), metadata=metadata)
            for hit_id, text, distance, metadata in zip(
                ids, documents, distances, metadatas, strict=False
            )
        ]
