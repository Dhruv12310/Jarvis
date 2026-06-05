"""Turn a natural-language question into search keywords for the keyword news connectors.

The markets/fundamentals connectors read tickers straight from the raw query, but a keyword news
API (GNews /search, GDELT) does badly with a conversational question full of stopwords - "what is
going on around the world right now" matches almost nothing. This strips question words, stopwords,
and generic news filler, leaving the salient terms. An EMPTY result is a meaningful signal: "no
specific topic" -> the caller falls back to top headlines (GNews) or a broad query (GDELT). Purely
deterministic (no LLM), so the trust boundary and the deterministic-first rule both hold.
"""

from __future__ import annotations

import re

# Stopwords + question words + generic news/time filler. A question made only of these ("what's
# happening in the world right now") reduces to "" -> the broad/top-headlines fallback fires; a
# question with a real subject ("latest news on Ukraine") keeps that subject ("Ukraine").
_STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "at",
    "for",
    "with",
    "about",
    "from",
    "by",
    "as",
    "into",
    "over",
    "out",
    "up",
    "down",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "am",
    "do",
    "does",
    "did",
    "has",
    "have",
    "had",
    "s",
    "i",
    "me",
    "my",
    "you",
    "your",
    "we",
    "our",
    "us",
    "it",
    "its",
    "this",
    "that",
    "these",
    "those",
    "there",
    "their",
    "them",
    "they",
    "he",
    "she",
    "his",
    "her",
    "what",
    "whats",
    "which",
    "who",
    "whom",
    "where",
    "when",
    "why",
    "how",
    "can",
    "could",
    "would",
    "should",
    "will",
    "shall",
    "may",
    "might",
    "must",
    "tell",
    "show",
    "give",
    "find",
    "get",
    "got",
    "know",
    "want",
    "see",
    "going",
    "happening",
    "happen",
    "look",
    "looking",
    "doing",
    # generic news / time filler -> these alone should trigger the broad fallback
    "news",
    "headline",
    "headlines",
    "update",
    "updates",
    "latest",
    "current",
    "currently",
    "recent",
    "recently",
    "today",
    "now",
    "right",
    "around",
    "world",
    "global",
    "worldwide",
    "international",
    "general",
    "story",
    "stories",
    "article",
    "articles",
    "please",
    "going-on",
}
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'&.-]*")


def keywords(text: str) -> str:
    """Salient search terms from a query (original case preserved), or "" when it is all filler."""
    # Compare with apostrophes removed so contractions match a stopword ("what's" -> "whats").
    kept = [
        token
        for token in _WORD.findall(text or "")
        if token.lower().replace("'", "") not in _STOPWORDS
    ]
    return " ".join(kept)
