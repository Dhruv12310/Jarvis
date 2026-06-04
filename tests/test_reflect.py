"""Reflection synthesis: the LLM sees only the assembled block; only well-typed + grounded insights
survive; verbatim reuse is dropped; survivors are written as `reflection` memories.
"""

import json
from datetime import UTC, datetime
from types import SimpleNamespace

from jarvis.proactivity.context import Context
from jarvis.proactivity.reflect import _PROMPT, reflect, synthesize


class _FakeLLM:
    def __init__(self, insights):
        self._insights = insights
        self.prompt = None

    def generate(self, prompt, *, format=None, think=None):
        self.prompt = prompt
        return json.dumps({"insights": self._insights})


def _ctx(block="CTX", ids=("m1", "signals")):
    return Context(block=block, source_ids=frozenset(ids))


def test_synthesize_sends_only_the_assembled_block_to_the_llm():
    llm = _FakeLLM([])

    synthesize(_ctx(block="THE ASSEMBLED BLOCK"), llm)

    assert llm.prompt == _PROMPT.format(block="THE ASSEMBLED BLOCK")  # grounding, byte-for-byte


def test_synthesize_keeps_a_grounded_typed_insight():
    llm = _FakeLLM([{"kind": "interest", "content": "likes systems languages", "links": ["m1"]}])

    [insight] = synthesize(_ctx(), llm)

    assert insight.kind == "interest" and insight.links == ["m1"]


def test_synthesize_drops_ungrounded_and_malformed_items():
    llm = _FakeLLM(
        [
            {"kind": "interest", "content": "ok", "links": ["m1"]},  # valid
            {"kind": "interest", "content": "no link", "links": []},  # ungrounded
            {"kind": "interest", "content": "bad id", "links": ["nope"]},  # link doesn't resolve
            {"kind": "banana", "content": "bad kind", "links": ["m1"]},  # invalid kind
            {"content": "missing kind", "links": ["m1"]},  # missing required field
        ]
    )

    out = synthesize(_ctx(), llm)

    assert [i.content for i in out] == ["ok"]


def test_synthesize_returns_empty_on_garbage_output():
    class _Bad:
        def generate(self, prompt, **kwargs):
            return "not json"

    assert synthesize(_ctx(), _Bad()) == []


class _MemStore:
    def __init__(self):
        self.saved = []

    def save(self, record):
        self.saved.append(record)


def test_reflect_writes_reflection_memories_and_drops_verbatim_reuse():
    now = datetime(2026, 6, 3, 9, tzinfo=UTC)
    memories = [SimpleNamespace(id="m1", content="I want to learn rust")]
    llm = _FakeLLM(
        [
            {
                "kind": "interest",
                "content": "The user is learning a systems language",
                "links": ["m1"],
            },
            {"kind": "observation", "content": "I want to learn rust", "links": ["m1"]},  # verbatim
        ]
    )
    store = _MemStore()

    written = reflect(
        signals_since=[], memories=memories, goals=[], llm=llm, memory_store=store, now=now
    )

    assert len(written) == 1  # the verbatim copy was dropped (reflection must abstract)
    assert store.saved[0].type == "reflection"
    assert store.saved[0].source == "reflection"
    assert store.saved[0].links == ["m1"]
