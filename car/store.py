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
    service: str        # e.g. "oil_change", "tire_rotation"
    notes: str = ""


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

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Vehicle":
        log = [ServiceLogEntry(**e) for e in d.get("service_log", [])]
        return cls(**{**d, "service_log": log})

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


def load_vehicles(path: Path = DATA_FILE) -> list[Vehicle]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    return [Vehicle.from_dict(d) for d in raw["vehicles"]]


def save_vehicles(vehicles: list[Vehicle], path: Path = DATA_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"vehicles": [v.to_dict() for v in vehicles]}
    path.write_text(json.dumps(payload, indent=2) + "\n")
