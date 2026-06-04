"""The User Model (Core §5.3): the inspectable, materialized profile reflection builds and the
ranker (5b) scores against. All math here is DETERMINISTIC - no LLM (a boundary test guards it).

`confidence_after` is the pinned update law (rises on re-confirmation, decays on contradiction). The
ONE guard that keeps usefulness from drifting to engagement (Core §8): a pure-frequency interest
does NOT raise an amplifiable `weight` - only a GOAL-LINKED topic does. Frequency is recorded (its
confidence rises) but never amplified, so a compulsion the user repeats can't train the ranker.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime


@dataclass(frozen=True)
class Interest:
    topic: str
    weight: float  # amplifiable signal for the ranker; 0.0 unless the topic is goal-linked
    confidence: float  # how sure we are this is a real pattern (rises on re-confirmation)
    last_updated: datetime


@dataclass(frozen=True)
class Rhythm:
    pattern: str
    confidence: float


@dataclass(frozen=True)
class Preference:
    key: str
    value: str
    confidence: float


@dataclass(frozen=True)
class UserModel:
    interests: list[Interest] = field(default_factory=list)
    rhythms: list[Rhythm] = field(default_factory=list)
    preferences: list[Preference] = field(default_factory=list)
    goals: list = field(
        default_factory=list
    )  # merged live from the Phase-2 store, never stored here
    updated_at: datetime | None = None


def to_dict(model: UserModel) -> dict:
    """Serialize the derived parts (NOT goals - those are read live) for the materialized store."""
    return {
        "interests": [
            {
                "topic": i.topic,
                "weight": i.weight,
                "confidence": i.confidence,
                "last_updated": i.last_updated.isoformat(),
            }
            for i in model.interests
        ],
        "rhythms": [{"pattern": r.pattern, "confidence": r.confidence} for r in model.rhythms],
        "preferences": [
            {"key": p.key, "value": p.value, "confidence": p.confidence} for p in model.preferences
        ],
        "updated_at": model.updated_at.isoformat() if model.updated_at else None,
    }


def from_dict(data: dict) -> UserModel:
    return UserModel(
        interests=[
            Interest(
                i["topic"], i["weight"], i["confidence"], datetime.fromisoformat(i["last_updated"])
            )
            for i in data.get("interests", [])
        ],
        rhythms=[Rhythm(r["pattern"], r["confidence"]) for r in data.get("rhythms", [])],
        preferences=[
            Preference(p["key"], p["value"], p["confidence"]) for p in data.get("preferences", [])
        ],
        updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
    )


def confidence_after(current: float, observation: str, *, alpha: float, gamma: float) -> float:
    """Pinned, pure update law. confirm -> c + alpha*(1-c) (saturates toward 1); contradict ->
    c - gamma*c (toward 0). Clamped to [0,1], monotonic, reproducible."""
    if observation == "confirm":
        return min(1.0, current + alpha * (1.0 - current))
    if observation == "contradict":
        return max(0.0, current - gamma * current)
    return current


def is_goal_linked(topic: str, goals) -> bool:
    """A topic is amplifiable only if it serves a declared goal - never pure frequency (Core §8)."""
    t = topic.lower()
    return any(t in getattr(g, "description", "").lower() for g in goals)


def merge(
    model: UserModel, insight, goals, *, now: datetime, alpha: float, gamma: float
) -> UserModel:
    """Deterministically fold a reflection insight into the model. Observations are not merged
    (they live as reflection memories); only interest/rhythm/preference shape the profile."""
    if insight.kind == "interest" and insight.topic:
        return _merge_interest(model, insight.topic, goals, now=now, alpha=alpha, gamma=gamma)
    if insight.kind == "rhythm":
        return _merge_rhythm(model, insight.content, now=now, alpha=alpha, gamma=gamma)
    if insight.kind == "preference":
        return _merge_preference(model, insight.content, now=now, alpha=alpha, gamma=gamma)
    return model


def suppress_interest(model: UserModel, topic: str, *, now: datetime, gamma: float) -> UserModel:
    """User correction: a topic I do not want amplified -> decay its weight + confidence."""
    interests = []
    for it in model.interests:
        if it.topic == topic:
            interests.append(
                Interest(
                    topic=it.topic,
                    weight=confidence_after(it.weight, "contradict", alpha=0.0, gamma=gamma),
                    confidence=confidence_after(
                        it.confidence, "contradict", alpha=0.0, gamma=gamma
                    ),
                    last_updated=now,
                )
            )
        else:
            interests.append(it)
    return replace(model, interests=interests, updated_at=now)


def _merge_interest(model, topic, goals, *, now, alpha, gamma):
    amplifiable = is_goal_linked(topic, goals)
    interests = list(model.interests)
    for i, it in enumerate(interests):
        if it.topic == topic:
            interests[i] = Interest(
                topic=topic,
                # weight rises ONLY for goal-linked topics; frequency alone never amplifies.
                weight=confidence_after(it.weight, "confirm", alpha=alpha, gamma=gamma)
                if amplifiable
                else it.weight,
                confidence=confidence_after(it.confidence, "confirm", alpha=alpha, gamma=gamma),
                last_updated=now,
            )
            return replace(model, interests=interests, updated_at=now)
    interests.append(Interest(topic, alpha if amplifiable else 0.0, alpha, now))
    return replace(model, interests=interests, updated_at=now)


def _merge_rhythm(model, pattern, *, now, alpha, gamma):
    rhythms = list(model.rhythms)
    for i, r in enumerate(rhythms):
        if r.pattern == pattern:
            rhythms[i] = Rhythm(
                pattern, confidence_after(r.confidence, "confirm", alpha=alpha, gamma=gamma)
            )
            return replace(model, rhythms=rhythms, updated_at=now)
    rhythms.append(Rhythm(pattern, alpha))
    return replace(model, rhythms=rhythms, updated_at=now)


def _merge_preference(model, value, *, now, alpha, gamma):
    preferences = list(model.preferences)
    for i, p in enumerate(preferences):
        if p.value == value:
            preferences[i] = Preference(
                p.key, p.value, confidence_after(p.confidence, "confirm", alpha=alpha, gamma=gamma)
            )
            return replace(model, preferences=preferences, updated_at=now)
    preferences.append(Preference("note", value, alpha))
    return replace(model, preferences=preferences, updated_at=now)
