"""The Heartbeat scheduler (Core §6/§9): the always-on pass that makes Jarvis proactive.

`tick` is the pure, testable unit - on each beat it lets reflection fire if its §7.4 trigger says
so, runs the candidate -> rank -> gate pass (which surfaces the top-K or, usually, nothing), and
once a day at the digest hour assembles the daily briefing that Phase 2 deferred. `run` is the thin
loop around it. Delivery decisions (abstention, caps, quiet hours) all live in the engine; the
scheduler only decides WHEN to run, never what is useful.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from datetime import date, datetime

from jarvis.config import config


@dataclass(frozen=True)
class SchedulerState:
    last_digest_date: date | None = None  # so the daily digest fires once per day, not every tick


@dataclass(frozen=True)
class TickResult:
    reflected: bool  # reflection fired this tick (its trigger crossed the threshold)
    surfaced: int  # suggestions surfaced this tick (0 is the common, correct case)
    digest: str | None  # the daily briefing text when the digest fired, else None


def tick(service, now: datetime, state: SchedulerState) -> tuple[SchedulerState, TickResult]:
    """One beat: reflect-if-due, run the suggestion pass, deliver the daily digest at its hour."""
    reflected = service.reflect() > 0  # force=False: only fires when §7.4 says so
    surfaced = len(service.suggestions(now=now))
    digest = None
    if now.hour == config.digest_hour and state.last_digest_date != now.date():
        digest = service.briefing()  # the auto-briefing, finally automatic (deferred from Phase 2)
        state = replace(state, last_digest_date=now.date())
    return state, TickResult(reflected=reflected, surfaced=surfaced, digest=digest)


def run(service, *, deliver=print) -> None:  # pragma: no cover - the thin always-on loop
    """Beat forever on the always-on Heartbeat box. `deliver` renders a fired digest."""
    state = SchedulerState()
    while True:
        state, result = tick(service, datetime.now().astimezone(), state)
        if result.digest:
            deliver(result.digest)
        time.sleep(config.scheduler_interval_seconds)
