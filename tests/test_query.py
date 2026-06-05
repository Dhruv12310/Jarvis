"""keywords(): salient search terms from a natural-language question (deterministic)."""

from jarvis.query import keywords


def test_keeps_specific_subject():
    assert keywords("latest global news on Ukraine") == "Ukraine"
    assert keywords("what's the news about OpenAI partnerships") == "OpenAI partnerships"


def test_preserves_original_case_and_short_tickers():
    # GNews search is fed these verbatim; the existing news connector test expects q == "AI".
    assert keywords("AI") == "AI"
    assert keywords("how is NVDA doing") == "NVDA"


def test_broad_question_reduces_to_empty():
    # All filler -> "" is the signal for the top-headlines / broad-query fallback.
    assert keywords("what is going on around the world right now?") == ""
    assert keywords("show me the latest world news today") == ""
    assert keywords("") == ""


def test_strips_punctuation():
    assert keywords("news about Tesla, please!") == "Tesla"
