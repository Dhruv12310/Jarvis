"""Structured results returned by JarvisService.

Capability methods return data, not printed strings, so every front-end (CLI, GUI, voice) renders
the same facts its own way. Goals/memories return the existing `Goal`/`MemoryRecord` value objects;
the briefing returns plain text; these two wrap the cases that need an extra flag.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AskResult:
    text: str
    grounded: bool  # True = knowledge pipeline (cited); False = labeled plain chat
    cached: bool


@dataclass(frozen=True)
class AgendaResult:
    events: list  # list[CalendarEvent]; empty when not connected or genuinely no events
    connected: bool  # False = calendar not authorized yet (front-end can prompt calendar-auth)


@dataclass(frozen=True)
class Quote:
    """A point-in-time market quote for the cockpit's stock tiles. Every figure comes from the
    markets connector (Finnhub /quote); `change` is computed deterministically (price - prev_close),
    never invented. `currency` is fixed USD (free /quote is US equities) rather than guessed."""

    symbol: str
    price: float
    change: float  # absolute price change vs prev close (price - prev_close)
    change_pct: float
    prev_close: float
    currency: str = "USD"


@dataclass(frozen=True)
class SymbolMatch:
    """A candidate ticker for a free-text company search (so the user can 'track any company' by
    name, not just by exact ticker). symbol + a human description, straight from Finnhub /search."""

    symbol: str
    description: str


@dataclass(frozen=True)
class GoalFeedItem:
    """One piece of public info attached to a goal, with a deterministic WHY (no LLM verdict)."""

    title: str
    detail: str  # one-line human fact (a connector Item.detail, or a grounded snippet)
    why: str  # deterministic: "relates to goal #<id>: <desc>" (+ the matched term)
    source: str  # "markets" | "news" | "hn" | "knowledge" | "suggestion"
    kind: str  # "market" | "news" | "story" | "snippet" | "suggestion"
    url: str | None = None


@dataclass(frozen=True)
class GoalFeed:
    """An active goal and the public info surfaced for it (possibly empty for that goal). The PULL
    view the cockpit shows so the user SEES their goals driving relevant info."""

    goal_id: int
    goal: str  # the goal description, so the front-end renders a header without a second join
    items: list  # list[GoalFeedItem]


@dataclass(frozen=True)
class CompanyNews:
    """One recent company headline (from the fundamentals connector's /company-news facet)."""

    title: str
    source: str
    url: str | None = None


@dataclass(frozen=True)
class CompanyView:
    """A deterministic company profile assembled from the fundamentals connector - every figure
    comes straight from Finnhub, never an LLM. Empty fields (or `note` set) mean a facet was
    unavailable / the key is missing; the front-end shows what's present and never invents a number.
    The optional cloud Deep Dive (Tier 2) is a SEPARATE call that synthesizes over this data."""

    symbol: str
    name: str | None = None
    industry: str | None = None
    exchange: str | None = None
    market_cap: str | None = None  # human-formatted ("$4.58T"); raw value lives in `metrics`
    ipo: str | None = None
    weburl: str | None = None
    metrics: dict | None = None  # financials facet: pe, margins, growth, 52-week, eps, beta, ...
    recommendation: str | None = None  # one-line analyst buy/hold/sell summary
    news: list = field(default_factory=list)  # list[CompanyNews]
    sources: list = field(default_factory=list)  # list[str], e.g. ["Finnhub"]
    note: str | None = None  # set when there is no data / no key, so the surface can explain why


@dataclass(frozen=True)
class NewsItem:
    """One world-news headline for the News view + globe. A deterministic passthrough of a GDELT
    article - every field comes straight from the connector, never an LLM. `country` is GDELT's full
    source-country name (e.g. "United States"); the front-end maps it to a globe centroid. Empty
    fields just mean GDELT omitted them; never invented."""

    title: str
    source: str  # publishing domain (GDELT `domain`)
    url: str | None = None
    country: str | None = None  # GDELT sourcecountry, full name; None if absent
    published: str | None = None  # "YYYY-MM-DD" derived from seendate; None if absent
    image: str | None = None  # social image URL; None if absent
