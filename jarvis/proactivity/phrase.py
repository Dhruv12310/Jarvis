"""Card phrasing - the ONLY LLM call in the 5b engine, and it is phrasing ONLY.

The model turns an already-decided suggestion (its deterministic reason + local payload) into a
short card body. It never scores, selects, or invents the "why" - ranking and the explanation are
code (rank.py). Grounded: the prompt carries only this candidate's reason + payload, nothing else.
"""

from __future__ import annotations

_PROMPT = (
    "Write a single short, friendly sentence telling the user about this. Use ONLY the facts "
    "given; do not invent anything, do not add advice.\n\nFACT: {reason}\nDETAILS: {payload}"
)


def phrase(scored, chat) -> str:
    """Render a one-line card body via the chat callable (the local LLM). Phrasing only."""
    candidate = scored.candidate
    prompt = _PROMPT.format(reason=candidate.provenance.reason, payload=candidate.payload)
    return chat(prompt).strip()
