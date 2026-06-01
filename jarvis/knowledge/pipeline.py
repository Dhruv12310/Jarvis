"""Knowledge pipeline: route -> deterministic fetch -> grounded answer.

Returns ``None`` when no connector applies (the CLI then falls back to plain chat). A failing
connector is contained (treated as empty) so one bad source cannot crash the answer. ``cached`` is
true only when every queried connector served from cache (drives the CLI ``(cached)`` marker).
"""

from __future__ import annotations

from dataclasses import dataclass

from jarvis.connectors.base import Connector, ConnectorResult
from jarvis.knowledge.answerer import Answerer
from jarvis.knowledge.router import Router


@dataclass(frozen=True)
class Answer:
    text: str
    cached: bool


class Knowledge:
    def __init__(
        self, router: Router, connectors: dict[str, Connector], answerer: Answerer
    ) -> None:
        self._router = router
        self._connectors = connectors
        self._answerer = answerer

    def ask(self, question: str) -> Answer | None:
        selected = [
            self._connectors[name]
            for name in self._router.route(question)
            if name in self._connectors
        ]
        if not selected:
            return None  # no connector -> CLI falls back to plain chat

        results: list[ConnectorResult] = []
        for connector in selected:
            try:
                results.append(connector.fetch(question))
            except Exception:
                continue  # a failing source is treated as empty, never crashes the answer

        cached = bool(results) and all(
            getattr(connector, "last_was_cache_hit", False) for connector in selected
        )
        return Answer(text=self._answerer.answer(question, results), cached=cached)
