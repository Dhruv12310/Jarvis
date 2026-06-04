"""Watchlist store CRUD (kind in {symbol, topic}). User-owned, public terms only - these are the
ONLY terms that ever reach a collector's outbound query (the trust boundary for candidate fetch)."""

from jarvis.stores.sqlite_store import SQLiteStructuredStore


def test_watchlist_add_list_remove_is_idempotent(tmp_path):
    store = SQLiteStructuredStore(tmp_path / "j.db")
    store.add_watch("symbol", "NVDA")
    store.add_watch("topic", "local LLMs")
    store.add_watch("symbol", "NVDA")  # idempotent on the (kind, value) primary key

    items = store.get_watchlist()
    assert {(w.kind, w.value) for w in items} == {("symbol", "NVDA"), ("topic", "local LLMs")}

    store.remove_watch("symbol", "NVDA")
    assert {(w.kind, w.value) for w in store.get_watchlist()} == {("topic", "local LLMs")}
