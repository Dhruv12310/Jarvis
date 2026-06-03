"""Calendar read path: event normalization (timed/all-day/missing fields), the events.list query
params, day_bounds date math, and the OAuth guard paths that don't need a live Google token.
"""

from datetime import UTC, date, datetime

import pytest

from jarvis.calendar import oauth
from jarvis.calendar.client import CalendarClient, day_bounds


class _FakeEvents:
    def __init__(self, items, captured):
        self._items = items
        self._captured = captured

    def list(self, **kwargs):
        self._captured.update(kwargs)
        return self

    def execute(self):
        return {"items": self._items}


class _FakeService:
    """Stands in for the googleapiclient Calendar resource: service.events().list(...).execute()."""

    def __init__(self, items):
        self.captured = {}
        self._events = _FakeEvents(items, self.captured)

    def events(self):
        return self._events


def test_list_events_normalizes_a_timed_event():
    service = _FakeService(
        [
            {
                "id": "e1",
                "summary": "Standup",
                "location": "Zoom",
                "start": {"dateTime": "2026-06-01T09:30:00+00:00"},
                "end": {"dateTime": "2026-06-01T10:00:00+00:00"},
            }
        ]
    )

    [event] = CalendarClient(service).list_events("min", "max")

    assert event.id == "e1"
    assert event.summary == "Standup"
    assert event.location == "Zoom"
    assert event.all_day is False
    assert event.start == datetime(2026, 6, 1, 9, 30, tzinfo=UTC)
    assert event.end == datetime(2026, 6, 1, 10, 0, tzinfo=UTC)


def test_list_events_normalizes_an_all_day_event():
    service = _FakeService(
        [
            {
                "id": "e2",
                "summary": "Holiday",
                "start": {"date": "2026-06-01"},
                "end": {"date": "2026-06-02"},
            }
        ]
    )

    [event] = CalendarClient(service).list_events("min", "max")

    assert event.all_day is True
    assert event.start.tzinfo is not None  # normalized to tz-aware (no naive/aware mixing)
    assert event.start.date() == date(2026, 6, 1)
    assert event.location is None


def test_event_without_summary_gets_a_placeholder():
    service = _FakeService(
        [
            {
                "id": "e3",
                "start": {"dateTime": "2026-06-01T09:00:00+00:00"},
                "end": {"dateTime": "2026-06-01T09:30:00+00:00"},
            }
        ]
    )

    [event] = CalendarClient(service).list_events("min", "max")

    assert event.summary == "(no title)"


def test_list_events_requests_expanded_ordered_primary_calendar():
    service = _FakeService([])

    CalendarClient(service).list_events("MIN", "MAX", max_results=5)

    assert service.captured == {
        "calendarId": "primary",
        "timeMin": "MIN",
        "timeMax": "MAX",
        "singleEvents": True,
        "orderBy": "startTime",
        "maxResults": 5,
    }


def test_no_items_returns_empty():
    assert CalendarClient(_FakeService([])).list_events("min", "max") == []


def test_day_bounds_spans_one_local_day():
    now = datetime(2026, 6, 1, 14, 30, tzinfo=UTC)

    time_min, time_max = day_bounds(now)

    assert time_min == "2026-06-01T00:00:00+00:00"
    assert time_max == "2026-06-02T00:00:00+00:00"


def test_load_credentials_returns_none_without_a_token(tmp_path):
    assert oauth.load_credentials(token_path=tmp_path / "token.json") is None


def test_authorize_without_credentials_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        oauth.authorize(
            credentials_path=tmp_path / "credentials.json", token_path=tmp_path / "token.json"
        )
