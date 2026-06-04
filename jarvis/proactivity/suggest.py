"""The suggestion engine (Core Stage 6): generate -> rank -> phrase -> Suggestion records.

`build` is the pure heart: it runs the deterministic generators + ranker over an injected
EngineState, then asks the LLM to phrase ONLY the survivors. The "why" is built here in code from
the candidate's provenance + the ranker's per-feature contributions - never an LLM verdict. The
facade (JarvisService) gathers the EngineState (the I/O) and persists the returned Suggestions.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from jarvis.proactivity import phrase as _phrase
from jarvis.proactivity import rank
from jarvis.proactivity.generators import generate_all
from jarvis.stores.structured import Suggestion


def _why(scored) -> str:
    """Deterministic explanation: the generator's reason + the top score drivers."""
    drivers = sorted(scored.contributions.items(), key=lambda kv: kv[1], reverse=True)
    top = ", ".join(f"{name} {value:+.2f}" for name, value in drivers[:2] if value)
    reason = scored.candidate.provenance.reason
    return f"{reason} (drivers: {top})" if top else reason


def build(state, *, chat, now: datetime) -> list[Suggestion]:
    """Generate candidates, rank + gate them, phrase the survivors into Suggestions (or none)."""
    suggestions = []
    for scored in rank.select(generate_all(state), state):
        candidate = scored.candidate
        suggestions.append(
            Suggestion(
                id=uuid4().hex,
                created_at=now,
                candidate_type=candidate.type,
                entity_key=candidate.entity_key,
                content=_phrase.phrase(scored, chat),
                why=_why(scored),
                source_ids=list(candidate.provenance.source_ids),
                features=dict(scored.contributions),
                score=scored.score,
                surfaced=True,
                channel="feed",
            )
        )
    return suggestions
