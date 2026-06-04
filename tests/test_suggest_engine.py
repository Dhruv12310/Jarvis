"""The suggestion engine: generate -> rank -> phrase. The card body is LLM-written, but the "why"
is deterministic code that resolves to real source ids; abstention yields no suggestions."""

from datetime import UTC, datetime
from types import SimpleNamespace

from jarvis.proactivity import suggest
from jarvis.proactivity.candidate import EngineState
from jarvis.proactivity.user_model import UserModel

NOW = datetime(2026, 6, 3, 9, 0, tzinfo=UTC)


def _fake_chat(prompt):
    return "You have a goal due soon."  # the LLM body (phrasing only)


def _goal(gid=1, description="ship 5b", priority="high"):
    return SimpleNamespace(
        id=gid,
        description=description,
        priority=priority,
        status="active",
        deadline=NOW,
        created_at=NOW,
        progress=0.0,
    )


def test_build_produces_a_card_with_llm_body_and_deterministic_why():
    state = EngineState(now=NOW, goals=[_goal()], user_model=UserModel())

    built = suggest.build(state, chat=_fake_chat, now=NOW)

    assert len(built) == 1
    s = built[0]
    assert s.content == "You have a goal due soon."  # the LLM wrote the body
    assert s.source_ids == ["goal:1"]  # the "why" resolves to a real record
    assert s.candidate_type == "goal_nudge" and s.surfaced is True
    assert s.entity_key == "goal:1" and s.channel == "feed"
    assert s.why  # deterministic provenance + drivers, not an LLM verdict


def test_build_abstains_to_empty_when_nothing_clears_threshold():
    state = EngineState(now=NOW, user_model=UserModel())  # no goals/budget/events -> no candidates

    assert suggest.build(state, chat=_fake_chat, now=NOW) == []
