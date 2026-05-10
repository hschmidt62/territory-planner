"""Vehicle data persistence. The repo's data/vehicles.json is the source of truth."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = REPO_ROOT / "data" / "vehicles.json"


@dataclass
class ServiceLogEntry:
    date: str           # YYYY-MM-DD
    odometer: int
    service: str        # e.g. "oil_and_filter", "tire_rotation"
    notes: str = ""


@dataclass
class NotificationPolicy:
    """How aggressively to nag once an item is overdue."""
    enabled: bool = True
    # Day count from "first alerted" -> at this many days, the alert escalates.
    # Default: louder at week 1, alarming at week 2, pre-fill booking at week 3.
    escalation_days: list[int] = field(default_factory=lambda: [7, 14, 21])
    # Frequency in days between alerts at each escalation level (0..len(escalation_days)).
    # Default = daily at every level. Set [7, 7, 1, 1] for "weekly first, then daily".
    frequency_by_level: list[int] = field(default_factory=lambda: [1, 1, 1, 1])


@dataclass
class DueState:
    """Per-due-item nag state. Keyed by item_id (e.g. 'service:oil_and_filter')."""
    item_id: str
    first_alerted_at: str           # YYYY-MM-DD; date this item was first flagged
    last_alerted_at: str = ""       # YYYY-MM-DD; date of most recent alert
    alert_count: int = 0
    snoozed_until: str = ""         # YYYY-MM-DD; suppress alerts until this date
    acknowledged_at: str = ""       # YYYY-MM-DD; user said "I'll handle it" (silences nag)


@dataclass
class Vehicle:
    vin: str
    nickname: str = ""
    # NHTSA-decoded fields. Filled in by the workflow on first run if blank.
    make: str = ""
    model: str = ""
    model_year: int | None = None
    trim: str = ""
    # Owner-supplied
    odometer: int | None = None
    odometer_updated: str = ""           # YYYY-MM-DD when odometer was logged
    annual_mileage_estimate: int = 12000 # used to project mileage between updates
    dealer: dict[str, str] = field(default_factory=dict)  # {name, city, phone, scheduler_url}
    owner_contact: dict[str, str] = field(default_factory=dict)  # {name, phone, telegram_chat_id}
    service_log: list[ServiceLogEntry] = field(default_factory=list)
    # Recalls already acknowledged so we don't re-alert. Keyed by NHTSA campaign id.
    acknowledged_recalls: list[str] = field(default_factory=list)
    # Nag policy and per-item state
    notification_policy: NotificationPolicy = field(default_factory=NotificationPolicy)
    due_state: list[DueState] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Vehicle":
        d = dict(d)
        d["service_log"] = [ServiceLogEntry(**e) for e in d.get("service_log", [])]
        d["due_state"] = [DueState(**e) for e in d.get("due_state", [])]
        if "notification_policy" in d and isinstance(d["notification_policy"], dict):
            d["notification_policy"] = NotificationPolicy(**d["notification_policy"])
        return cls(**d)

    def projected_odometer(self, on: date | None = None) -> int | None:
        """Linearly project current odometer from the last logged reading."""
        if self.odometer is None or not self.odometer_updated:
            return self.odometer
        on = on or date.today()
        try:
            last = date.fromisoformat(self.odometer_updated)
        except ValueError:
            return self.odometer
        days = max(0, (on - last).days)
        return self.odometer + int(self.annual_mileage_estimate * days / 365)

    def get_due_state(self, item_id: str) -> DueState | None:
        for s in self.due_state:
            if s.item_id == item_id:
                return s
        return None


def load_vehicles(path: Path = DATA_FILE) -> list[Vehicle]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    return [Vehicle.from_dict(d) for d in raw["vehicles"]]


def save_vehicles(vehicles: list[Vehicle], path: Path = DATA_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"vehicles": [v.to_dict() for v in vehicles]}
    path.write_text(json.dumps(payload, indent=2) + "\n")
