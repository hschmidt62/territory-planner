"""Daily check: decode any new VIN, project mileage, find due services and recalls.

Outputs a Markdown report on stdout. Exits 0 always; the caller decides what
to do with the report (open a GitHub Issue, send a Telegram message, etc.).
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from .store import Vehicle, load_vehicles, save_vehicles
from .decode import decode_vin
from .recalls import fetch_recalls, summarize
from .intervals import for_make, Interval


def _hydrate(v: Vehicle) -> bool:
    """Decode VIN if make/model/year are blank. Returns True if anything changed."""
    if v.make and v.model and v.model_year:
        return False
    try:
        info = decode_vin(v.vin)
    except Exception as e:  # noqa: BLE001
        print(f"<!-- VIN decode failed for {v.vin}: {e} -->", file=sys.stderr)
        return False
    changed = False
    for attr in ("make", "model", "trim"):
        if not getattr(v, attr) and info.get(attr):
            setattr(v, attr, info[attr])
            changed = True
    if not v.model_year and info.get("model_year"):
        v.model_year = info["model_year"]
        changed = True
    return changed


def _last_service(v: Vehicle, name: str) -> tuple[int | None, str | None]:
    """Most recent (odometer, date) for a given service name, or (None, None)."""
    matches = [e for e in v.service_log if e.service == name]
    if not matches:
        return (None, None)
    last = max(matches, key=lambda e: e.date)
    return (last.odometer, last.date)


def _due(v: Vehicle, interval: Interval, today: date) -> tuple[bool, str]:
    """Return (is_due, reason)."""
    last_mi, last_date = _last_service(v, interval.name)
    proj = v.projected_odometer(today)

    # Mileage check (uses projected odometer if no service has been logged yet)
    if interval.mileage is not None:
        baseline = last_mi if last_mi is not None else 0
        if proj is not None and proj - baseline >= interval.mileage:
            mi_since = proj - baseline
            return (True, f"~{mi_since:,} mi since last (interval {interval.mileage:,} mi)")

    # Time check
    if interval.months is not None:
        if last_date:
            try:
                last = date.fromisoformat(last_date)
            except ValueError:
                last = None
        else:
            last = None
        if last:
            months_since = (today.year - last.year) * 12 + (today.month - last.month)
            if months_since >= interval.months:
                return (True, f"{months_since} months since last (interval {interval.months} months)")
        # No service ever logged: only flag time-only items if odometer was first
        # logged > N months ago, so a brand new entry doesn't immediately fire.

    return (False, "")


def render_report(vehicles: list[Vehicle], today: date | None = None) -> str:
    today = today or date.today()
    out: list[str] = []
    any_alert = False

    for v in vehicles:
        title = " ".join(
            part for part in (str(v.model_year or ""), v.make, v.model, v.trim) if part
        ).strip() or v.vin
        out.append(f"## {v.nickname or title}")
        out.append(f"- VIN: `{v.vin}`")
        if v.odometer is not None:
            proj = v.projected_odometer(today)
            note = f" (projected today: ~{proj:,} mi)" if proj and proj != v.odometer else ""
            out.append(f"- Odometer: {v.odometer:,} mi as of {v.odometer_updated or 'unknown'}{note}")
        else:
            out.append("- Odometer: **not logged yet** — see instructions below")

        # Service intervals
        due_items: list[str] = []
        for interval in for_make(v.make):
            is_due, reason = _due(v, interval, today)
            if is_due:
                due_items.append(f"  - **{interval.description}** — {reason}")
        if due_items:
            any_alert = True
            out.append("")
            out.append("### Service due")
            out.extend(due_items)

        # Recalls
        try:
            recalls = fetch_recalls(v.make, v.model, v.model_year or 0)
        except Exception as e:  # noqa: BLE001
            recalls = []
            print(f"<!-- recall fetch failed for {v.vin}: {e} -->", file=sys.stderr)
        new_recalls = [r for r in recalls if r.get("NHTSACampaignNumber") not in v.acknowledged_recalls]
        if new_recalls:
            any_alert = True
            out.append("")
            out.append(f"### Open recalls ({len(new_recalls)})")
            for r in new_recalls:
                s = summarize(r)
                out.append(f"- **{s['component']}** ({s['campaign_id']})")
                if s["consequence"]:
                    out.append(f"  - Risk: {s['consequence'][:300]}")
                if s["remedy"]:
                    out.append(f"  - Remedy: {s['remedy'][:300]}")

        if not due_items and not new_recalls and v.odometer is not None:
            out.append("- All clear.")

        out.append("")

    if not any_alert and all(v.odometer is not None for v in vehicles):
        return ""  # caller can use empty string as "nothing to report"

    header = f"# Car maintenance check — {today.isoformat()}\n\n"
    return header + "\n".join(out).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    vehicles = load_vehicles()
    if not vehicles:
        print("No vehicles configured in data/vehicles.json", file=sys.stderr)
        return 0

    changed = any(_hydrate(v) for v in vehicles)
    if changed:
        save_vehicles(vehicles)

    report = render_report(vehicles)
    if report:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
