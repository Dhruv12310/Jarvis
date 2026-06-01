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
