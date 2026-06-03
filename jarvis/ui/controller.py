"""AppController: maps UI actions to JarvisService calls and posts result cards to the feed.

Pure (no Flet), so every action is unit-tested with a faked service; `ui/app.py` wires Flet widgets
to these methods. The controller holds NO business logic of its own - it only calls the facade and
shapes the result into a feed card. Shortcut-button actions (Slice 3) extend this same class.
"""

from __future__ import annotations

from jarvis.redact import redact
from jarvis.service import JarvisService
from jarvis.ui.feed import Card, Feed

# The "Markets/News" shortcut is a preset question through the same grounded ask path.
_MARKETS_QUERY = "What's happening in markets and tech news today?"


class AppController:
    def __init__(self, service: JarvisService, feed: Feed) -> None:
        self._service = service
        self._feed = feed

    def show_briefing(self) -> None:
        try:
            self._feed.post_card(Card("Daily briefing", self._service.briefing(), "briefing"))
        except Exception as exc:
            self._post_error(exc)

    def ask(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self._feed.post_card(Card("You", text, "chat"))  # echo the question
        try:
            result = self._service.ask(text)
        except Exception as exc:
            self._post_error(exc)
            return
        title = "Jarvis (cached)" if result.cached else "Jarvis"
        self._feed.post_card(Card(title, result.text, "answer" if result.grounded else "chat"))

    # --- shortcut-button actions (Slice 3) -------------------------------------------------

    def show_agenda(self) -> None:
        try:
            result = self._service.agenda()
        except Exception as exc:
            self._post_error(exc)
            return
        if not result.connected:
            body = "Not connected. Run: python -m jarvis calendar-auth"
        elif not result.events:
            body = "No events today."
        else:
            body = "\n".join(_event_line(event) for event in result.events)
        self._feed.post_card(Card("Today's calendar", body, "agenda"))

    def ask_markets_news(self) -> None:
        self.ask(_MARKETS_QUERY)  # already guarded via ask()

    def add_goal(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        try:
            goal = self._service.add_goal(text)
        except Exception as exc:
            self._post_error(exc)
            return
        self._feed.post_card(Card("Goal added", f"#{goal.id}  {goal.description}", "goal"))

    def _post_error(self, exc: Exception) -> None:
        # A backend failure (e.g. Ollama down) posts an error card instead of crashing the GUI, so
        # the feed keeps receiving. Redacted, since exception text reaches a user surface.
        self._feed.post_card(Card("Error", redact(str(exc)), "error"))


def _event_line(event) -> str:
    when = "all day" if event.all_day else f"{event.start:%H:%M}-{event.end:%H:%M}"
    location = f" @ {event.location}" if event.location else ""
    return f"- {when} {event.summary}{location}"
