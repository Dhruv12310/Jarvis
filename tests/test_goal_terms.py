"""Deterministic goal -> public-term extraction: pure, repeatable, leaks no private text."""

from jarvis.proactivity.goal_terms import extract_terms


def test_extracts_uppercase_ticker_as_symbol():
    terms = extract_terms("Grow my NVDA position before earnings")
    assert "NVDA" in terms.symbols


def test_lowercase_company_stays_topic_not_symbol():
    terms = extract_terms("learn how amazon scaled aws")  # no all-caps ticker
    assert terms.symbols == []
    assert any("amazon" in topic.lower() for topic in terms.topics)


def test_not_tickers_and_stopwords_are_dropped():
    terms = extract_terms("Build an AI app with the LLM")  # AI/LLM are not tickers
    assert terms.symbols == []
    assert all(
        w.lower() not in {"the", "an", "build", "with"}
        for topic in terms.topics
        for w in topic.split()
    )


def test_bigram_topic_is_emitted():
    terms = extract_terms("get better at personal finance budgeting")
    assert any(topic.lower() == "personal finance" for topic in terms.topics)  # a phrase


def test_saas_company_goal_yields_topics_not_bogus_tickers():
    terms = extract_terms("Build a LLC Saas comapny")  # the user's real goal (typo and all)
    assert terms.symbols == []  # LLC is not a ticker; nothing all-caps that resolves
    assert terms.topics  # but it still produces topic terms so the feed is non-empty


def test_empty_goal_yields_no_terms():
    terms = extract_terms("")
    assert terms.symbols == [] and terms.topics == []


def test_is_deterministic():
    a = extract_terms("track TSLA and renewable energy news")
    b = extract_terms("track TSLA and renewable energy news")
    assert a == b  # frozen dataclass equality, repeatable
