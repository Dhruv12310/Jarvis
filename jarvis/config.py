"""Single configuration location for Jarvis.

All settings resolve from ``JARVIS_*`` environment variables (loaded from an optional, git-ignored
``.env``) with safe, local-first defaults. Phase 0 holds no secrets. Business logic reads from the
module-level ``config`` singleton rather than touching ``os.environ`` directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # load a local .env if present; a no-op otherwise

# Repo root is the parent of the jarvis/ package; data/ lives alongside the source.
_ROOT = Path(__file__).resolve().parent.parent
_DATA = _ROOT / "data"


@dataclass(frozen=True)
class Config:
    """Resolved Jarvis settings. Field factories re-read the environment on each construction,
    so tests can override via env vars and a fresh ``Config()`` reflects them."""

    llm_model: str = field(default_factory=lambda: os.environ.get("JARVIS_LLM_MODEL", "qwen3:14b"))
    embed_model: str = field(
        default_factory=lambda: os.environ.get("JARVIS_EMBED_MODEL", "nomic-embed-text")
    )
    ollama_host: str = field(
        default_factory=lambda: os.environ.get("JARVIS_OLLAMA_HOST", "http://localhost:11434")
    )
    db_path: Path = field(
        default_factory=lambda: Path(os.environ.get("JARVIS_DB_PATH", str(_DATA / "jarvis.db")))
    )
    vector_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("JARVIS_VECTOR_DIR", str(_DATA / "chroma")))
    )

    def ensure_dirs(self) -> None:
        """Create the data directories on demand. They are git-ignored and never committed."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.vector_dir.mkdir(parents=True, exist_ok=True)


# Module-level singleton: import this everywhere instead of re-reading the environment.
config = Config()
