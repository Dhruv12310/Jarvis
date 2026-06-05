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
    # Tier 2 cloud escalation (Anthropic) - the controlled exception. Empty key = local-only: the
    # Model Router reports "unavailable" and Deep Dive is gracefully disabled. The key is read from
    # ANTHROPIC_API_KEY (the SDK's own convention), not a JARVIS_ name, so the standard env works.
    anthropic_api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
    cloud_model: str = field(
        default_factory=lambda: os.environ.get("JARVIS_CLOUD_MODEL", "claude-sonnet-4-6")
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
    # Finance (Phase 4) Plaid - the opt-in OUTBOUND source. Secrets via .env (git-ignored), never
    # committed. Empty = Plaid disabled (the local CSV/OFX import is the default path).
    plaid_client_id: str = field(
        default_factory=lambda: os.environ.get("JARVIS_PLAID_CLIENT_ID", "")
    )
    plaid_secret: str = field(default_factory=lambda: os.environ.get("JARVIS_PLAID_SECRET", ""))
    plaid_access_token: str = field(
        default_factory=lambda: os.environ.get("JARVIS_PLAID_ACCESS_TOKEN", "")
    )
    plaid_environment: str = field(
        default_factory=lambda: os.environ.get("JARVIS_PLAID_ENV", "sandbox")
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
    # Fundamentals (profile/financials/recommendation/news) change slowly: cached far longer than
    # quotes so a company view costs at most a handful of Finnhub calls per hour.
    cache_ttl_fundamentals: int = field(
        default_factory=lambda: int(os.environ.get("JARVIS_CACHE_TTL_FUNDAMENTALS", "3600"))
    )
    # GDELT global news refreshes ~every 15 min and rate-limits bursts hard, so cache ~that long.
    cache_ttl_gdelt: int = field(
        default_factory=lambda: int(os.environ.get("JARVIS_CACHE_TTL_GDELT", "900"))
    )
    # arXiv papers move slowly and arXiv asks for ~1 req/3s, so cache them for an hour.
    cache_ttl_arxiv: int = field(
        default_factory=lambda: int(os.environ.get("JARVIS_CACHE_TTL_ARXIV", "3600"))
    )
    arxiv_max_results: int = field(
        default_factory=lambda: int(os.environ.get("JARVIS_ARXIV_MAX_RESULTS", "10"))
    )
    # Goal-aware research ranking (Phase C). Deterministic relevance = w_overlap*term-overlap +
    # w_recency*exp(-lambda*age) + w_source*source-prior. Per-source priors favor papers, then news.
    research_w_overlap: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_RESEARCH_W_OVERLAP", "1.0"))
    )
    research_w_recency: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_RESEARCH_W_RECENCY", "0.5"))
    )
    research_w_source: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_RESEARCH_W_SOURCE", "0.4"))
    )
    research_recency_lambda: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_RESEARCH_RECENCY_LAMBDA", "0.02"))
    )
    research_source_weights: dict = field(
        default_factory=lambda: {
            "arxiv": 1.0,
            "news": 0.8,
            "gdelt": 0.8,
            "hn": 0.7,
            "knowledge": 0.6,
            "markets": 0.6,
        }
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

    # Phase 5 proactivity. Reflection fires when accumulated signal FUEL since the last reflection
    # crosses the threshold (§7.4). Confidence updates: rise = c + alpha*(1-c); decay = c - gamma*c.
    reflection_threshold: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_REFLECTION_THRESHOLD", "5.0"))
    )
    confidence_alpha: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_CONFIDENCE_ALPHA", "0.3"))
    )
    confidence_gamma: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_CONFIDENCE_GAMMA", "0.3"))
    )

    # Phase 5b proactivity engine. Candidate generators fire within these deterministic horizons.
    urgency_horizon_hours: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_URGENCY_HORIZON_HOURS", "72"))
    )
    stale_goal_days: int = field(
        default_factory=lambda: int(os.environ.get("JARVIS_STALE_GOAL_DAYS", "14"))
    )
    budget_near_fraction: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_BUDGET_NEAR_FRACTION", "0.1"))
    )
    recurring_horizon_days: int = field(
        default_factory=lambda: int(os.environ.get("JARVIS_RECURRING_HORIZON_DAYS", "5"))
    )
    market_move_pct: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_MARKET_MOVE_PCT", "3.0"))
    )

    # Usefulness ranker (§7.2). Hand-set beta weights (learned in 5c); the threshold is
    # ABSOLUTE and HIGH so abstention (show nothing) is the default. Caps are STRUCTURAL - no
    # score can raise volume. quiet hours + the enable flag are the hard DND gate.
    beta_goal: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_BETA_GOAL", "1.0"))
    )
    beta_urgency: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_BETA_URGENCY", "1.0"))
    )
    beta_interest: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_BETA_INTEREST", "1.0"))
    )
    beta_timing: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_BETA_TIMING", "0.3"))
    )
    beta_novelty: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_BETA_NOVELTY", "0.3"))
    )
    beta_fatigue: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_BETA_FATIGUE", "1.0"))
    )
    usefulness_threshold: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_USEFULNESS_THRESHOLD", "1.0"))
    )
    suggestions_per_window: int = field(
        default_factory=lambda: int(os.environ.get("JARVIS_SUGGESTIONS_PER_WINDOW", "3"))
    )
    suggestion_window_hours: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_SUGGESTION_WINDOW_HOURS", "24"))
    )
    per_category_cap: int = field(
        default_factory=lambda: int(os.environ.get("JARVIS_PER_CATEGORY_CAP", "1"))
    )
    # Goal-driven feed (PULL view). Per-goal cap on FETCHED items (connector + snippet); attached
    # standing suggestions are not volume-capped. A pull surface, so the cap is for focus, not the
    # strict abstention the PUSH ranker enforces.
    goal_feed_per_goal_cap: int = field(
        default_factory=lambda: int(os.environ.get("JARVIS_GOAL_FEED_PER_GOAL_CAP", "4"))
    )
    entity_cooldown_hours: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_ENTITY_COOLDOWN_HOURS", "48"))
    )
    novelty_lambda: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_NOVELTY_LAMBDA", "0.02"))
    )
    quiet_hours_start: int = field(
        default_factory=lambda: int(os.environ.get("JARVIS_QUIET_HOURS_START", "22"))
    )
    quiet_hours_end: int = field(
        default_factory=lambda: int(os.environ.get("JARVIS_QUIET_HOURS_END", "7"))
    )
    proactivity_enabled: bool = field(
        default_factory=lambda: os.environ.get("JARVIS_PROACTIVITY_ENABLED", "1") != "0"
    )
    # Feedback (§7.5/5c): learning rate for the per-feature ranker weight nudges.
    feedback_lr: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_FEEDBACK_LR", "0.1"))
    )
    # Explore/exploit (§7.3): per-category dismissal backoff = base * 2^(n-1) days, capped.
    category_cooldown_base_days: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_CATEGORY_COOLDOWN_BASE_DAYS", "1"))
    )
    category_cooldown_cap_days: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_CATEGORY_COOLDOWN_CAP_DAYS", "30"))
    )
    # Scheduler (§6/§9): the Heartbeat beat interval and the hour the daily digest/briefing fires.
    digest_hour: int = field(default_factory=lambda: int(os.environ.get("JARVIS_DIGEST_HOUR", "7")))
    scheduler_interval_seconds: int = field(
        default_factory=lambda: int(os.environ.get("JARVIS_SCHEDULER_INTERVAL", "3600"))
    )
    # File operations (cockpit shortcut bar). Deterministic filesystem create/list with full-disk
    # reach by design (no sandbox); the off-loopback write guard lives in the API layer. Set
    # JARVIS_FS_WRITES_ENABLED=0 to kill create_file/create_folder entirely (list stays read-only).
    fs_writes_enabled: bool = field(
        default_factory=lambda: os.environ.get("JARVIS_FS_WRITES_ENABLED", "1") != "0"
    )

    def ensure_dirs(self) -> None:
        """Create the data directories on demand. They are git-ignored and never committed."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.vector_dir.mkdir(parents=True, exist_ok=True)


# Module-level singleton: import this everywhere instead of re-reading the environment.
config = Config()
