"""Daily briefing: deterministic DATA block (all three sections, empty handling) and that the LLM
is fed only that block. Inputs are duck-typed via SimpleNamespace (no calendar/store deps needed).
"""

from datetime import UTC, datetime
from types import SimpleNamespace

from jarvis.briefing import _PROMPT, BriefingData, phrase, to_data_block


def _event(summary, start, end, *, location=None, all_day=False):
    return SimpleNamespace(
        summary=summary, start=start, end=end, location=location, all_day=all_day
    )


def _data(*, events=(), goals=(), digest=None):
    return BriefingData(
        when=datetime(2026, 6, 3, 8, 0, tzinfo=UTC),
        events=list(events),
        goals=list(goals),
        digest=digest,
    )


def test_data_block_contains_all_three_sections():
    data = _data(
        events=[
            _event(
                "Standup", datetime(2026, 6, 3, 9, 30), datetime(2026, 6, 3, 10, 0), location="Zoom"
            )
        ],
        goals=[SimpleNamespace(description="learn rust")],
        digest="markets up 1% [1]",
    )

    block = to_data_block(data)

    assert "Wednesday, June 03, 2026" in block
    assert "09:30-10:00 Standup @ Zoom" in block
    assert "learn rust" in block
    assert "markets up 1% [1]" in block


def test_data_block_handles_all_empty_sections():
    block = to_data_block(_data())

    assert "(no events today)" in block
    assert "(none)" in block  # goals + digest


def test_data_block_includes_a_finance_line_when_present():
    data = _data()
    data = BriefingData(
        when=data.when, events=[], goals=[], digest=None, finance="Spent $42.50 so far this month."
    )

    block = to_data_block(data)

    assert "Finance:" in block
    assert "Spent $42.50 so far this month." in block


def test_all_day_event_is_labeled():
    data = _data(
        events=[_event("Holiday", datetime(2026, 6, 3), datetime(2026, 6, 4), all_day=True)]
    )

    assert "all day Holiday" in to_data_block(data)


def test_phrase_feeds_only_the_block_to_the_llm():
    data = _data(goals=[SimpleNamespace(description="ship phase 2")])
    captured = {}

    def fake_generate(prompt):
        captured["prompt"] = prompt
        return "the briefing"

    result = phrase(data, fake_generate)

    assert result == "the briefing"
    # The LLM sees exactly the instruction + assembled block, nothing else.
    assert captured["prompt"].endswith(to_data_block(data))
    assert "ship phase 2" in captured["prompt"]


def test_phrase_sends_only_the_block_nothing_else():
    # Trust boundary: a private detail in the data must reach the model ONLY via the assembled
    # block, and the prompt must be EXACTLY instruction+block (no extra context smuggled in).
    data = _data(goals=[SimpleNamespace(description="call Dr. Smith re: biopsy")])
    captured = {}

    phrase(data, lambda p: captured.setdefault("p", p))

    assert captured["p"] == _PROMPT.format(block=to_data_block(data))


def test_phrase_preserves_a_digest_citation_in_the_block():
    data = _data(digest="rate cut expected [2]")

    captured = {}
    phrase(data, lambda p: captured.setdefault("p", p))

    assert "[2]" in captured["p"]
