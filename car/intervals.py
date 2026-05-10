"""Manufacturer service intervals.

Each interval has a `mileage` (miles between services) and/or `months` (time
between services). The first one to elapse triggers the service. Severe-duty
schedules are not used here; if you tow, off-road, or live somewhere extreme,
shorten oil & rotation to 3,750 mi.

Sources: Subaru 2024-2025 Warranty & Maintenance Booklet (generic gasoline,
non-turbo, normal-duty schedule). Hybrid and turbo models differ slightly.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Interval:
    name: str
    mileage: int | None       # miles between services (None = time-only)
    months: int | None        # months between services (None = mileage-only)
    description: str = ""


# Subaru normal-duty intervals. Used when the decoded make is "Subaru".
# These match Outback, Forester, Crosstrek, Ascent, Legacy, Impreza, BRZ
# closely enough for a reminder system; precise spec lives in the booklet.
SUBARU_INTERVALS: list[Interval] = [
    Interval("oil_and_filter", 6000, 6, "Engine oil & filter"),
    Interval("tire_rotation", 6000, 6, "Tire rotation"),
    Interval("cabin_air_filter", 30000, None, "Cabin air filter"),
    Interval("engine_air_filter", 30000, None, "Engine air filter"),
    Interval("brake_fluid", 30000, 36, "Brake fluid replacement"),
    Interval("coolant_inspect", 30000, None, "Inspect coolant"),
    Interval("differential_fluid", 30000, None, "Front/rear differential gear oil"),
    Interval("transfer_case_oil", 30000, None, "Transfer case oil (CVT models)"),
    Interval("spark_plugs", 60000, None, "Spark plugs (iridium)"),
    Interval("cvt_fluid_inspect", 30000, None, "Inspect CVT fluid"),
    Interval("coolant_replace", 137500, 132, "Replace engine coolant (first time)"),
]

DEFAULT_INTERVALS: list[Interval] = [
    Interval("oil_and_filter", 5000, 6, "Engine oil & filter"),
    Interval("tire_rotation", 6000, 6, "Tire rotation"),
    Interval("cabin_air_filter", 20000, None, "Cabin air filter"),
    Interval("engine_air_filter", 30000, None, "Engine air filter"),
    Interval("brake_fluid", 30000, 36, "Brake fluid replacement"),
]


def for_make(make: str) -> list[Interval]:
    if make.strip().lower() == "subaru":
        return SUBARU_INTERVALS
    return DEFAULT_INTERVALS
