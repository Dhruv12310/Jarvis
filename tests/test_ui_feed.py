"""UI feed + controller (pure, no Flet launched): cards render the facade's results and `post_card`
is the receive surface. The controller is driven with a faked JarvisService.
"""

from jarvis.results import AskResult
from jarvis.ui.controller import AppController
from jarvis.ui.feed import Card, Feed


class _FakeService:
    def __init__(self, *, briefing="the briefing", answer=None):
        self._briefing = briefing
        self._answer = answer or AskResult(text="the answer", grounded=True, cached=False)
        self.asked: list[str] = []

    def briefing(self) -> str:
        return self._briefing

    def ask(self, text: str) -> AskResult:
        self.asked.append(text)
        return self._answer


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
