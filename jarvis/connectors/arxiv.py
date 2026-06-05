"""Academic research connector via the arXiv API (recent papers for a topic).

Outbound HTTP only to arXiv. KEYLESS and dependency-free beyond httpx (already approved) - the Atom
feed is parsed with the stdlib (xml.etree.ElementTree), so no arXiv SDK enters the dependency set.
Where GNews/GDELT answer "what's in the news", this answers "what's the latest research on X", which
is what powers goal-aware paper suggestions. Like the other connectors it NEVER raises: a transport
error, a non-200 (arXiv asks for ~1 req/3s; a 429 just yields nothing and the long TTL cache absorbs
polling), or malformed XML all degrade to an empty result. The abs URL is normalized to its
version-less form so the same paper resurfacing as v2 dedups against v1 downstream.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import httpx

from jarvis.config import config
from jarvis.connectors.base import Connector, ConnectorResult, Item, Source

_URL = "https://export.arxiv.org/api/query"
# Every Atom path must be namespace-qualified; arxiv: holds primary_category, atom: the rest.
_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
_VERSION = re.compile(r"v\d+$")  # strip the trailing vN so v1/v2 of one paper share an id/url


class ArxivConnector(Connector):
    name = "arxiv"
    description = (
        "Recent academic research papers from arXiv (CS/ML/AI and other fields): titles, "
        "abstracts, authors, and dates for a topic - the source for 'latest research on X'."
    )

    def __init__(self, client: httpx.Client | None = None, max_results: int | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=30.0, headers={"User-Agent": "jarvis-arxiv/1.0 (personal assistant)"}
        )
        self._max = max_results if max_results is not None else config.arxiv_max_results

    def fetch(self, query: str) -> ConnectorResult:
        source = Source(name="arXiv", url="https://arxiv.org/")
        query = query.strip()
        if not query:
            return ConnectorResult(source=source, items=[], query=query)
        params = {
            "search_query": f"all:{query}",  # sortBy/sortOrder are top-level, never in search_query
            "start": "0",
            "max_results": str(self._max),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        try:
            response = self._client.get(_URL, params=params)
        except httpx.HTTPError:
            return ConnectorResult(source=source, items=[], query=query)
        if response.status_code != 200:  # rate limit / outage -> no items, never raises
            return ConnectorResult(source=source, items=[], query=query)
        try:
            root = ET.fromstring(response.content)  # bytes, so the XML encoding decl is honored
        except ET.ParseError:
            return ConnectorResult(source=source, items=[], query=query)
        items = [item for entry in root.findall("atom:entry", _NS) if (item := _to_item(entry))]
        return ConnectorResult(source=source, items=items, query=query)


def _to_item(entry: ET.Element) -> Item | None:
    title = " ".join((entry.findtext("atom:title", "", _NS) or "").split())
    if not title:
        return None
    abstract = (entry.findtext("atom:summary", "", _NS) or "").strip()
    authors = [
        name.strip()
        for a in entry.findall("atom:author/atom:name", _NS)
        if (name := (a.text or "")).strip()
    ]
    published = entry.findtext("atom:published", "", _NS) or ""
    primary = entry.find("arxiv:primary_category", _NS)
    categories = [c.get("term") for c in entry.findall("atom:category", _NS) if c.get("term")]
    # Disambiguate the multiple <link>s by attribute: the abstract page vs the PDF.
    links = {
        (ln.get("title") or ln.get("rel")): ln.get("href") for ln in entry.findall("atom:link", _NS)
    }
    abs_url = _VERSION.sub("", links.get("alternate") or "")  # version-less, so v1/v2 dedup
    raw_id = entry.findtext("atom:id", "", _NS) or ""
    return Item(
        title=title,
        detail=_byline(authors, published),
        url=abs_url or None,
        extra={
            "kind": "paper",
            "authors": authors,
            "published": published,
            "primary_category": primary.get("term") if primary is not None else None,
            "categories": categories,
            "pdf_url": links.get("pdf"),
            "abstract": abstract,
            "arxiv_id": _VERSION.sub("", raw_id),
        },
    )


def _byline(authors: list[str], published: str) -> str:
    """One human line: '<first author> et al., YYYY-MM-DD' (each part dropped when absent)."""
    who = ""
    if authors:
        who = f"{authors[0]} et al." if len(authors) > 1 else authors[0]
    date = published[:10] if len(published) >= 10 else ""
    return ", ".join(part for part in (who, date) if part)
