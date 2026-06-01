"""Config is the single settings location: env-overridable, safe local-first defaults."""

from jarvis.config import Config, config


def test_default_llm_model_is_qwen3_14b():
    assert Config().llm_model == "qwen3:14b"


def test_default_embed_model_is_nomic():
    assert Config().embed_model == "nomic-embed-text"


def test_default_ollama_host_is_localhost():
    assert Config().ollama_host == "http://localhost:11434"


def test_module_singleton_exposes_defaults():
    assert config.llm_model == "qwen3:14b"
    assert config.ollama_host.startswith("http://")


def test_env_override_is_respected(monkeypatch):
    monkeypatch.setenv("JARVIS_LLM_MODEL", "phi4")
    assert Config().llm_model == "phi4"


def test_default_data_paths_live_under_data_dir():
    cfg = Config()
    assert cfg.db_path.name == "jarvis.db"
    assert cfg.db_path.parent.name == "data"
    assert cfg.vector_dir.name == "chroma"


def test_ensure_dirs_creates_paths(tmp_path, monkeypatch):
    db = tmp_path / "sub" / "jarvis.db"
    vec = tmp_path / "vec"
    monkeypatch.setenv("JARVIS_DB_PATH", str(db))
    monkeypatch.setenv("JARVIS_VECTOR_DIR", str(vec))

    cfg = Config()
    cfg.ensure_dirs()

    assert db.parent.is_dir()
    assert vec.is_dir()


def test_ensure_dirs_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_DB_PATH", str(tmp_path / "d" / "jarvis.db"))
    monkeypatch.setenv("JARVIS_VECTOR_DIR", str(tmp_path / "v"))
    cfg = Config()

    cfg.ensure_dirs()
    cfg.ensure_dirs()  # second call must not raise

    assert (tmp_path / "d").is_dir()
    assert (tmp_path / "v").is_dir()


def test_api_keys_default_empty():
    cfg = Config()
    assert cfg.finnhub_api_key == ""
    assert cfg.gnews_api_key == ""


def test_api_keys_read_from_env(monkeypatch):
    monkeypatch.setenv("JARVIS_FINNHUB_API_KEY", "fk")
    monkeypatch.setenv("JARVIS_GNEWS_API_KEY", "gk")
    cfg = Config()
    assert cfg.finnhub_api_key == "fk"
    assert cfg.gnews_api_key == "gk"


def test_default_market_watchlist_is_a_ticker_tuple():
    cfg = Config()
    assert isinstance(cfg.market_watchlist, tuple)
    assert "AAPL" in cfg.market_watchlist
    assert "NVDA" in cfg.market_watchlist


def test_market_watchlist_from_env_is_parsed_and_uppercased(monkeypatch):
    monkeypatch.setenv("JARVIS_MARKET_WATCHLIST", "tsla, amd ,intc")
    assert Config().market_watchlist == ("TSLA", "AMD", "INTC")


def test_cache_ttls_have_sane_defaults():
    cfg = Config()
    assert cfg.cache_ttl_markets > 0
    assert cfg.cache_ttl_markets <= cfg.cache_ttl_hn  # markets refresh faster than HN
    assert cfg.cache_ttl_news > 0
