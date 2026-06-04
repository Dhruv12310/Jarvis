"""The Jarvis feed: an append-only list of cards (pure, no Flet).

`post_card` is the RECEIVE surface - in Phase 3 the user's actions post cards (briefing, answers,
shortcut results); in Phase 5 the proactivity engine will push `Suggestion` cards through the same
entry point. Phase 3 builds the surface only; it makes no cards on its own.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Card:
    title: str
    body: str
    kind: str  # briefing | answer | chat | agenda | goal | memory | suggestion | error
    why: str | None = None  # for proactive suggestions: the deterministic "why am I seeing this?"


class Feed:
    def __init__(self) -> None:
        self.cards: list[Card] = []

    def post_card(self, card: Card) -> None:
        self.cards.append(card)
