"""SQLiteCache: TTL get/set, expiry, overwrite, and persistence across instances."""

import time

from jarvis.cache.sqlite_cache import SQLiteCache


def _cache(tmp_path):
    return SQLiteCache(tmp_path / "cache.db")


def test_get_returns_value_while_fresh(tmp_path):
    cache = _cache(tmp_path)
    cache.set("k", "v", ttl_seconds=60)
    assert cache.get("k") == "v"


def test_get_missing_key_returns_none(tmp_path):
    assert _cache(tmp_path).get("absent") is None


def test_expired_value_returns_none(tmp_path):
    cache = _cache(tmp_path)
    cache.set("k", "v", ttl_seconds=0)  # expires immediately
    time.sleep(0.01)
    assert cache.get("k") is None


def test_set_overwrites_existing_key(tmp_path):
    cache = _cache(tmp_path)
    cache.set("k", "old", 60)
    cache.set("k", "new", 60)
    assert cache.get("k") == "new"


def test_values_persist_across_instances(tmp_path):
    path = tmp_path / "cache.db"
    first = SQLiteCache(path)
    first.set("k", "durable", 60)
    first.close()

    assert SQLiteCache(path).get("k") == "durable"
