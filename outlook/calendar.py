from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from .client import GraphClient

DEFAULT_EVENT_FIELDS = (
    "id,subject,start,end,location,organizer,attendees,isAllDay,onlineMeetingUrl,bodyPreview"
)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def list_events(
    client: GraphClient,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    top: int = 50,
    select: str = DEFAULT_EVENT_FIELDS,
) -> Iterator[dict[str, Any]]:
    """List events in [start, end). Defaults to the next 7 days."""
    start = start or datetime.now(timezone.utc)
    end = end or (start + timedelta(days=7))
    params = {
        "startDateTime": _iso(start),
        "endDateTime": _iso(end),
        "$top": min(top, 100),
        "$select": select,
        "$orderby": "start/dateTime",
    }
    yield from client.paged("/me/calendarView", params=params, max_items=top)


def create_event(
    client: GraphClient,
    *,
    subject: str,
    start: datetime,
    end: datetime,
    body: str = "",
    location: str | None = None,
    attendees: list[str] | None = None,
    timezone_name: str = "UTC",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "subject": subject,
        "body": {"contentType": "text", "content": body},
        "start": {"dateTime": _iso(start), "timeZone": timezone_name},
        "end": {"dateTime": _iso(end), "timeZone": timezone_name},
    }
    if location:
        payload["location"] = {"displayName": location}
    if attendees:
        payload["attendees"] = [
            {"emailAddress": {"address": a}, "type": "required"} for a in attendees
        ]
    return client.post("/me/events", json=payload)
