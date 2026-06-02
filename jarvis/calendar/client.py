"""Read-only Calendar client: list events and normalize them to a typed CalendarEvent.

The Google event resource is messy (timed vs all-day, optional summary/location); normalization
happens here so the rest of Jarvis sees clean values. ``day_bounds`` is pure date math
(deterministic, not the LLM's job). ``connect`` wires stored credentials into a ready client.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from jarvis.calendar.oauth import build_service, load_credentials


@dataclass(frozen=True)
class CalendarEvent:
    id: str
    summary: str
    start: datetime
    end: datetime
    location: str | None
    all_day: bool


class CalendarClient:
    def __init__(self, service) -> None:
        self._service = service

    def list_events(
        self, time_min: str, time_max: str, max_results: int = 20
    ) -> list[CalendarEvent]:
        # singleEvents expands recurrences into instances; orderBy="startTime" requires it.
        response = (
            self._service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=max_results,
            )
            .execute()
        )
        return [_to_event(item) for item in response.get("items", [])]


def connect(
    credentials_path: Path | None = None, token_path: Path | None = None
) -> CalendarClient | None:
    """Return a ready client, or None if the calendar has not been authorized yet."""
    creds = load_credentials(credentials_path, token_path)
    if creds is None:
        return None
    return CalendarClient(build_service(creds))


def day_bounds(now: datetime) -> tuple[str, str]:
    """RFC3339 [start-of-day, start-of-next-day) for ``now`` (must be tz-aware)."""
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.isoformat(), (start + timedelta(days=1)).isoformat()


def _to_event(item: dict) -> CalendarEvent:
    start = item["start"]
    return CalendarEvent(
        id=item["id"],
        summary=item.get("summary", "(no title)"),
        start=_parse_when(start),
        end=_parse_when(item["end"]),
        location=item.get("location"),
        all_day="date" in start,
    )


def _parse_when(when: dict) -> datetime:
    # All-day events carry "date" (YYYY-MM-DD); timed events carry RFC3339 "dateTime".
    return datetime.fromisoformat(when.get("dateTime") or when["date"])
