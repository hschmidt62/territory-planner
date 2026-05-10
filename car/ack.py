"""Parse acknowledgement / snooze / mileage commands from an Issue comment.

Recognized forms (case-insensitive, anywhere in the comment body):

  done <item_id>             # marks item as acknowledged today
  done <item_id> at <miles>  # ack + log a service entry at that odometer
  ack <item_id>              # silences nag without claiming the work was done
  snooze <item_id> 5d        # snooze for 5 days (also accepts 1w, 2w)
  unsnooze <item_id>         # clear snooze
  mileage <miles>            # update odometer (today's date)
  mileage <miles> on YYYY-MM-DD

Item IDs come from the Issue body (e.g. `service:oil_and_filter`, `recall:23V456`).
Multiple commands per comment are supported, one per line.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .store import (
    DueState,
    ServiceLogEntry,
    Vehicle,
    load_vehicles,
    save_vehicles,
)

ITEM_RE = r"(?P<item>(?:service|recall):[A-Za-z0-9_\-]+)"
MILES_RE = r"(?P<miles>\d{1,7})"
DATE_RE = r"(?P<on>\d{4}-\d{2}-\d{2})"
DURATION_RE = r"(?P<n>\d+)\s*(?P<unit>d|w)"

DONE_RE       = re.compile(rf"\bdone\s+{ITEM_RE}(?:\s+at\s+{MILES_RE})?", re.I)
ACK_RE        = re.compile(rf"\back\s+{ITEM_RE}", re.I)
SNOOZE_RE     = re.compile(rf"\bsnooze\s+{ITEM_RE}\s+{DURATION_RE}", re.I)
UNSNOOZE_RE   = re.compile(rf"\bunsnooze\s+{ITEM_RE}", re.I)
MILEAGE_RE    = re.compile(rf"\bmileage\s+{MILES_RE}(?:\s+on\s+{DATE_RE})?", re.I)


@dataclass
class Effect:
    summary: str


def _state_for(v: Vehicle, item_id: str) -> DueState:
    s = v.get_due_state(item_id)
    if s is None:
        s = DueState(item_id=item_id, first_alerted_at=date.today().isoformat())
        v.due_state.append(s)
    return s


def _service_name_from_item(item_id: str) -> str | None:
    if item_id.startswith("service:"):
        return item_id.split(":", 1)[1]
    return None


def apply_comment(vehicles: list[Vehicle], comment: str, today: date | None = None) -> list[Effect]:
    """Apply every recognized command in `comment` to the first vehicle.

    With multiple vehicles, this would need to be scoped (e.g. per VIN
    mentioned). For now we keep it simple: a single vehicle in vehicles.json.
    """
    today = today or date.today()
    if not vehicles:
        return []
    v = vehicles[0]
    effects: list[Effect] = []

    for m in DONE_RE.finditer(comment):
        item_id = m.group("item")
        miles = m.group("miles")
        s = _state_for(v, item_id)
        s.acknowledged_at = today.isoformat()
        sname = _service_name_from_item(item_id)
        if sname and miles:
            v.service_log.append(ServiceLogEntry(
                date=today.isoformat(), odometer=int(miles), service=sname,
                notes="logged via issue comment",
            ))
            effects.append(Effect(f"logged {sname} at {int(miles):,} mi and acknowledged {item_id}"))
        elif sname:
            v.service_log.append(ServiceLogEntry(
                date=today.isoformat(),
                odometer=v.odometer or 0,
                service=sname,
                notes="logged via issue comment (no mileage given)",
            ))
            effects.append(Effect(f"logged {sname} (no mileage given) and acknowledged {item_id}"))
        else:
            effects.append(Effect(f"acknowledged {item_id}"))
        if item_id.startswith("recall:"):
            cid = item_id.split(":", 1)[1]
            if cid not in v.acknowledged_recalls:
                v.acknowledged_recalls.append(cid)

    for m in ACK_RE.finditer(comment):
        item_id = m.group("item")
        s = _state_for(v, item_id)
        s.acknowledged_at = today.isoformat()
        effects.append(Effect(f"silenced {item_id} (not marked as done)"))

    for m in SNOOZE_RE.finditer(comment):
        item_id = m.group("item")
        n = int(m.group("n"))
        unit = m.group("unit").lower()
        days = n * (7 if unit == "w" else 1)
        s = _state_for(v, item_id)
        s.snoozed_until = (today + timedelta(days=days)).isoformat()
        effects.append(Effect(f"snoozed {item_id} until {s.snoozed_until}"))

    for m in UNSNOOZE_RE.finditer(comment):
        item_id = m.group("item")
        s = _state_for(v, item_id)
        s.snoozed_until = ""
        effects.append(Effect(f"unsnoozed {item_id}"))

    for m in MILEAGE_RE.finditer(comment):
        miles = int(m.group("miles"))
        when = m.group("on") or today.isoformat()
        if v.odometer is not None and miles < v.odometer:
            effects.append(Effect(f"refused mileage update: {miles:,} < recorded {v.odometer:,}"))
        else:
            v.odometer = miles
            v.odometer_updated = when
            effects.append(Effect(f"updated odometer to {miles:,} mi as of {when}"))

    return effects


def main(argv: list[str] | None = None) -> int:
    """CLI: read a comment body from stdin, apply, save, print summary."""
    comment = sys.stdin.read()
    vehicles = load_vehicles()
    effects = apply_comment(vehicles, comment)
    if effects:
        save_vehicles(vehicles)
        for e in effects:
            print(f"- {e.summary}")
    else:
        print("(no recognized commands)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
