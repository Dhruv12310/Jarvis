"""Intent router: the local LLM (Tier-1 conductor) picks which connectors apply to a question.

The model is constrained to JSON (``format="json"``). Output is validated against the known
connector names; anything unknown or malformed yields ``[]`` so the pipeline falls back to plain
chat. The LLM only routes here; it fetches nothing.
"""

from __future__ import annotations

import json

from jarvis.connectors.base import Connector
from jarvis.llm.client import LLMClient

_PROMPT = """You route a user question to data sources. Decide which sources (if any) should be
queried to answer it with live data. Reply with JSON only, of the form
{{"connectors": ["<name>", ...]}}, using only the source names listed below. Use an empty list if
none apply (for example general chit-chat, or questions unrelated to these sources).

Sources:
{sources}

Question: {question}
"""

# A JSON schema (not plain "json") so a thinking model is constrained to the exact shape rather than
# collapsing to {}. think=False keeps the mechanical routing step fast and deterministic-feeling.
_SCHEMA = {
    "type": "object",
    "properties": {"connectors": {"type": "array", "items": {"type": "string"}}},
    "required": ["connectors"],
}


class Router:
    def __init__(self, llm: LLMClient, connectors: list[Connector]) -> None:
        self._llm = llm
        self._connectors = connectors
        self._known = {c.name for c in connectors}

    def route(self, question: str) -> list[str]:
        sources = "\n".join(f"- {c.name}: {c.description}" for c in self._connectors)
        prompt = _PROMPT.format(sources=sources, question=question)
        raw = self._llm.generate(prompt, format=_SCHEMA, think=False)
        return [name for name in self._parse(raw) if name in self._known]

    @staticmethod
    def _parse(raw: str) -> list[str]:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
        names = data.get("connectors") if isinstance(data, dict) else None
        if not isinstance(names, list):
            return []
        return [name for name in names if isinstance(name, str)]
