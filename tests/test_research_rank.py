"""research_rank.rank(): deterministic relevance ordering of goal-feed items. Pure, offline."""

from datetime import UTC, datetime

from jarvis.proactivity.goal_terms import GoalTerms
from jarvis.proactivity.research_rank import rank
from jarvis.results import GoalFeedItem

NOW = datetime(2026, 6, 4, tzinfo=UTC)
TERMS = GoalTerms(symbols=[], topics=["personal finance", "budgeting"])


def _item(title, *, kind="paper", source="arxiv", detail="X et al., 2026-06-01"):
    return GoalFeedItem(title=title, detail=detail, why="w", source=source, kind=kind, url=title)


def test_higher_term_overlap_ranks_first():
    low = _item("Personal Finance with Deep Learning")  # 1 of 2 terms
    high = _item("Budgeting and Personal Finance Tools")  # 2 of 2 terms
    assert rank(TERMS, [low, high], now=NOW) == [high, low]


def test_zero_overlap_paper_is_dropped():
    good = _item("Personal Finance Models")
    irrelevant = _item("Quantum Chromodynamics on Lattices")
    out = rank(TERMS, [good, irrelevant], now=NOW)
    assert out == [good]  # the irrelevant paper is gated out


def test_zero_overlap_non_paper_is_kept():
    # News was fetched BY a goal term, so it is reordered but never dropped for a title miss.
    news = _item("Markets wobble on rate fears", kind="news", source="news")
    paper = _item("Personal Finance Models")
    out = rank(TERMS, [paper, news], now=NOW)
    assert set(out) == {paper, news}  # both survive
    assert out[0] == paper  # the matching paper still outranks the zero-overlap news


def test_recency_breaks_equal_overlap():
    newer = _item("Personal Finance A", detail="X et al., 2026-06-03")
    older = _item("Personal Finance B", detail="X et al., 2026-01-01")
    assert rank(TERMS, [older, newer], now=NOW) == [newer, older]


def test_missing_date_is_neutral_not_a_crash():
    dated = _item("Personal Finance A", detail="X et al., 2026-06-03")
    undated = _item("Personal Finance B", detail="no date here")
    out = rank(TERMS, [undated, dated], now=NOW)
    assert out == [dated, undated]  # recent (1.0) beats neutral (0.5) at equal overlap


def test_no_terms_preserves_input_order():
    a, b = _item("A", kind="news"), _item("B", kind="news")
    empty = GoalTerms(symbols=[], topics=[])
    assert rank(empty, [a, b], now=NOW) == [a, b]


def test_deterministic_across_runs():
    items = [
        _item("Budgeting and Personal Finance Tools"),
        _item("Personal Finance with Deep Learning"),
        _item("Personal Finance Models", detail="X et al., 2026-02-01"),
    ]
    assert rank(TERMS, list(items), now=NOW) == rank(TERMS, list(items), now=NOW)
