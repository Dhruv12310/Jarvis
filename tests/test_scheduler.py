"""The Heartbeat scheduler tick: reflect-if-due + surface each beat; the daily digest once a day."""

from datetime import UTC, datetime

from jarvis.proactivity import scheduler

DIGEST_HOUR = 7  # config default


class _FakeService:
    def __init__(self):
        self.calls = []
        self.briefings = 0

    def reflect(self):
        self.calls.append("reflect")
        return 0

    def suggestions(self, *, now=None):
        self.calls.append("suggestions")
        return []

    def briefing(self):
        self.calls.append("briefing")
        self.briefings += 1
        return "today: 1 event, 2 goals"


def test_tick_reflects_and_surfaces_every_beat_without_a_digest_off_hour():
    svc = _FakeService()
    now = datetime(2026, 6, 4, 9, 0, tzinfo=UTC)  # not the digest hour

    state, result = scheduler.tick(svc, now, scheduler.SchedulerState())

    assert "reflect" in svc.calls and "suggestions" in svc.calls
    assert result.digest is None and svc.briefings == 0


def test_daily_digest_fires_once_at_the_digest_hour():
    svc = _FakeService()
    morning = datetime(2026, 6, 4, DIGEST_HOUR, 0, tzinfo=UTC)

    state, first = scheduler.tick(svc, morning, scheduler.SchedulerState())
    _, second = scheduler.tick(svc, morning.replace(minute=45), state)

    assert first.digest is not None and svc.briefings == 1  # delivered once
    assert second.digest is None and svc.briefings == 1  # not again the same day
