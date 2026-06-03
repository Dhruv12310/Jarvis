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
    # Calendar (Phase 2) OAuth secrets. Both live in ./data/ (git-ignored): the OAuth client
    # downloaded from Google Cloud, and the user token minted on first `calendar-auth`.
    google_credentials_path: Path = field(
        default_factory=lambda: Path(
            os.environ.get("JARVIS_GOOGLE_CREDENTIALS", str(_DATA / "credentials.json"))
        )
    )
    google_token_path: Path = field(
        default_factory=lambda: Path(
            os.environ.get("JARVIS_GOOGLE_TOKEN", str(_DATA / "token.json"))
        )
    )
    # Voice (Phase 3), local on the Brain. STT auto-downloads from HuggingFace; drop to small/base
    # for lower latency. TTS points at a Piper voice the user downloads into ./data/ (git-ignored).
    stt_model: str = field(
        default_factory=lambda: os.environ.get("JARVIS_STT_MODEL", "large-v3-turbo")
    )
    tts_model_path: Path = field(
        default_factory=lambda: Path(
            os.environ.get("JARVIS_TTS_MODEL", str(_DATA / "piper" / "en_US-lessac-high.onnx"))
        )
    )

    # Phase 1: public-data connectors. An empty key means that connector reports "no key" rather
    # than fetching (it never invents data); the user fills these in .env.
    finnhub_api_key: str = field(
        default_factory=lambda: os.environ.get("JARVIS_FINNHUB_API_KEY", "")
    )
    gnews_api_key: str = field(default_factory=lambda: os.environ.get("JARVIS_GNEWS_API_KEY", ""))
    market_watchlist: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            t.strip().upper()
            for t in os.environ.get(
                "JARVIS_MARKET_WATCHLIST", "AAPL,MSFT,NVDA,GOOGL,AMZN,META,TSLA"
            ).split(",")
            if t.strip()
        )
    )
    # Per-connector cache TTLs (seconds): markets move fast, news/HN are calmer.
    cache_ttl_markets: int = field(
        default_factory=lambda: int(os.environ.get("JARVIS_CACHE_TTL_MARKETS", "60"))
    )
    cache_ttl_news: int = field(
        default_factory=lambda: int(os.environ.get("JARVIS_CACHE_TTL_NEWS", "300"))
    )
    cache_ttl_hn: int = field(
        default_factory=lambda: int(os.environ.get("JARVIS_CACHE_TTL_HN", "300"))
    )

    # Phase 2 memory retrieval (Core §7.1). Weights default to 1.0; lambda tunes recency
    # decay (per hour of age).
    memory_candidate_pool: int = field(
        default_factory=lambda: int(os.environ.get("JARVIS_MEMORY_POOL", "20"))
    )
    memory_recency_lambda: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_MEMORY_LAMBDA", "0.02"))
    )
    memory_w_rec: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_MEMORY_W_REC", "1.0"))
    )
    memory_w_imp: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_MEMORY_W_IMP", "1.0"))
    )
    memory_w_rel: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_MEMORY_W_REL", "1.0"))
    )

    def ensure_dirs(self) -> None:
        """Create the data directories on demand. They are git-ignored and never committed."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.vector_dir.mkdir(parents=True, exist_ok=True)


# Module-level singleton: import this everywhere instead of re-reading the environment.
config = Config()
