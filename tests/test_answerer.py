"""Answerer: the grounded prompt is built from fetched data only; empty -> couldn't-find path."""

from jarvis.connectors.base import ConnectorResult, Item, Source
from jarvis.knowledge.answerer import Answerer


class _CaptureLLM:
    def __init__(self):
        self.prompt = None

    def generate(self, prompt, *, format=None):
        self.prompt = prompt
        return "ANSWER"


def test_answer_includes_data_and_source_citation():
    llm = _CaptureLLM()
    results = [
        ConnectorResult(
            source=Source("Hacker News", "https://news.ycombinator.com/"),
            items=[Item("Title A", "100 points, 5 comments", "https://a.test")],
            query="q",
        )
    ]

    out = Answerer(llm).answer("what's new", results)

    assert out == "ANSWER"
    assert "Title A" in llm.prompt
    assert "Hacker News" in llm.prompt
    assert "only" in llm.prompt.lower()  # grounding instruction present


def test_empty_results_steer_to_couldnt_find():
    llm = _CaptureLLM()
    Answerer(llm).answer("q", [])
    assert "(no data found)" in llm.prompt
    assert "could not find" in llm.prompt.lower()


def test_results_with_empty_items_treated_as_no_data():
    llm = _CaptureLLM()
    Answerer(llm).answer("q", [ConnectorResult(Source("HN"), [], "q")])
    assert "(no data found)" in llm.prompt
