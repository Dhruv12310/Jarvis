"""VectorStore (Chroma backend): embed -> add -> similarity query returns the right doc on top.

Uses the deterministic fake embedder so the ranking assertion never depends on a live model.
"""

from jarvis.stores.chroma_store import ChromaVectorStore
from jarvis.stores.vector import VectorHit


def test_query_returns_the_matching_document_first(tmp_path, fake_embedder):
    store = ChromaVectorStore(tmp_path / "chroma")
    texts = [
        "buy groceries and milk",
        "schedule dentist appointment",
        "read a book about rust",
    ]
    for i, text in enumerate(texts):
        store.add(id=str(i), text=text, embedding=fake_embedder.embed(text))

    hits = store.query(fake_embedder.embed("schedule dentist appointment"), k=3)

    assert isinstance(hits[0], VectorHit)
    assert hits[0].text == "schedule dentist appointment"


def test_query_respects_k(tmp_path, fake_embedder):
    store = ChromaVectorStore(tmp_path / "chroma")
    for i in range(5):
        text = f"note number {i}"
        store.add(id=str(i), text=text, embedding=fake_embedder.embed(text))

    assert len(store.query(fake_embedder.embed("note number 2"), k=2)) == 2


def test_metadata_round_trips(tmp_path, fake_embedder):
    store = ChromaVectorStore(tmp_path / "chroma")
    text = "remember the alpha project"
    store.add(
        id="42", text=text, embedding=fake_embedder.embed(text), metadata={"project": "alpha"}
    )

    top = store.query(fake_embedder.embed(text), k=1)[0]

    assert top.id == "42"
    assert top.metadata == {"project": "alpha"}


def test_query_on_empty_store_returns_no_hits(tmp_path, fake_embedder):
    store = ChromaVectorStore(tmp_path / "chroma")

    assert store.query(fake_embedder.embed("anything"), k=5) == []


def test_query_k_larger_than_collection_is_clamped(tmp_path, fake_embedder):
    store = ChromaVectorStore(tmp_path / "chroma")
    for i, text in enumerate(["one apple", "two banana"]):
        store.add(id=str(i), text=text, embedding=fake_embedder.embed(text))

    hits = store.query(fake_embedder.embed("one apple"), k=10)

    assert len(hits) == 2
