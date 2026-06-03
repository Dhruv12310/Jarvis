"""UI feed + controller (pure, no Flet launched): cards render the facade's results and `post_card`
is the receive surface. The controller is driven with a faked JarvisService.
"""

from datetime import datetime
from types import SimpleNamespace

from jarvis.results import AgendaResult, AskResult
from jarvis.ui.controller import AppController
from jarvis.ui.feed import Card, Feed


class _FakeService:
    def __init__(self, *, briefing="the briefing", answer=None, agenda=None):
        self._briefing = briefing
        self._answer = answer or AskResult(text="the answer", grounded=True, cached=False)
        self._agenda = agenda if agenda is not None else AgendaResult(events=[], connected=False)
        self.asked: list[str] = []
        self.added_goals: list[str] = []

    def briefing(self) -> str:
        return self._briefing

    def ask(self, text: str) -> AskResult:
        self.asked.append(text)
        return self._answer

    def agenda(self) -> AgendaResult:
        return self._agenda

    def add_goal(self, text: str):
        self.added_goals.append(text)
        return SimpleNamespace(id=len(self.added_goals), description=text)


def _controller(service=None):
    feed = Feed()
    return AppController(service or _FakeService(), feed), feed


def test_post_card_appends_to_the_feed():
    feed = Feed()

    feed.post_card(Card("t", "b", "briefing"))

    assert feed.cards == [Card("t", "b", "briefing")]


def test_show_briefing_posts_a_briefing_card():
    controller, feed = _controller(_FakeService(briefing="today: nothing"))

    controller.show_briefing()

    assert feed.cards == [Card("Daily briefing", "today: nothing", "briefing")]


def test_ask_posts_the_question_then_a_grounded_answer():
    service = _FakeService(answer=AskResult(text="grounded", grounded=True, cached=False))
    controller, feed = _controller(service)

    controller.ask("what is up")

    assert service.asked == ["what is up"]
    assert feed.cards == [
        Card("You", "what is up", "chat"),
        Card("Jarvis", "grounded", "answer"),
    ]


def test_ask_marks_cached_and_labels_chat_fallback():
    controller, feed = _controller(
        _FakeService(answer=AskResult(text="from memory", grounded=False, cached=True))
    )

    controller.ask("hello")

    answer = feed.cards[-1]
    assert answer.title == "Jarvis (cached)"
    assert answer.kind == "chat"  # not grounded -> labeled chat


def test_ask_ignores_blank_input():
    service = _FakeService()
    controller, feed = _controller(service)

    controller.ask("   ")

    assert feed.cards == []
    assert service.asked == []


# --- shortcut buttons (Slice 3) ---------------------------------------------


def test_show_agenda_when_not_connected():
    controller, feed = _controller(_FakeService(agenda=AgendaResult(events=[], connected=False)))

    controller.show_agenda()

    assert feed.cards[0].kind == "agenda"
    assert "calendar-auth" in feed.cards[0].body


def test_show_agenda_lists_events():
    event = SimpleNamespace(
        summary="Standup",
        start=datetime(2026, 6, 3, 9, 30),
        end=datetime(2026, 6, 3, 10, 0),
        all_day=False,
        location="Zoom",
    )
    controller, feed = _controller(
        _FakeService(agenda=AgendaResult(events=[event], connected=True))
    )

    controller.show_agenda()

    assert "09:30-10:00 Standup @ Zoom" in feed.cards[0].body


def test_show_agenda_with_no_events():
    controller, feed = _controller(_FakeService(agenda=AgendaResult(events=[], connected=True)))

    controller.show_agenda()

    assert "No events today" in feed.cards[0].body


def test_markets_news_uses_the_preset_query():
    service = _FakeService()
    controller, feed = _controller(service)

    controller.ask_markets_news()

    assert service.asked == ["What's happening in markets and tech news today?"]
    assert feed.cards[-1].title.startswith("Jarvis")  # answer card posted


def test_add_goal_posts_a_card():
    service = _FakeService()
    controller, feed = _controller(service)

    controller.add_goal("learn rust")

    assert service.added_goals == ["learn rust"]
    assert feed.cards == [Card("Goal added", "#1  learn rust", "goal")]


def test_add_goal_ignores_blank():
    service = _FakeService()
    controller, feed = _controller(service)

    controller.add_goal("   ")

    assert feed.cards == []
    assert service.added_goals == []
