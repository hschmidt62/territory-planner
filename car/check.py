"""Daily check.

Decodes any new VIN, projects mileage, identifies due services and recalls,
runs the nag policy, persists DueState updates, and emits two artifacts:

- /tmp/report.md  : the rolling Issue body (current full state)
- /tmp/today.md   : today's nag comment (empty if nothing to alert about)
- /tmp/title.txt  : suggested Issue title with the highest active escalation
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .store import (
    DueState,
    Vehicle,
    load_vehicles,
    save_vehicles,
)
from .decode import decode_vin
from .recalls import fetch_recalls, summarize
from .intervals import for_make, Interval
from .policy import decide, escalation_level, LEVEL_EMOJI, LEVEL_LABEL


# ----- Hydration ------------------------------------------------------------

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


# ----- Due-item detection ---------------------------------------------------

@dataclass
class DueItem:
    item_id: str        # stable id, e.g. "service:oil_and_filter" or "recall:23V456"
    kind: str           # "service" | "recall"
    title: str          # human-readable
    detail: str = ""    # one-liner reason / consequence
    booking_hint: str = ""  # extra advice (e.g. recall remedy)


def _last_service(v: Vehicle, name: str) -> tuple[int | None, str | None]:
    matches = [e for e in v.service_log if e.service == name]
    if not matches:
        return (None, None)
    last = max(matches, key=lambda e: e.date)
    return (last.odometer, last.date)


def _service_due(v: Vehicle, interval: Interval, today: date) -> str:
    """Return reason string if the service is currently due, else ''."""
    last_mi, last_date = _last_service(v, interval.name)
    proj = v.projected_odometer(today)

    if interval.mileage is not None and proj is not None:
        baseline = last_mi if last_mi is not None else 0
        if proj - baseline >= interval.mileage:
            return f"~{proj - baseline:,} mi since last (interval {interval.mileage:,} mi)"

    if interval.months is not None and last_date:
        try:
            last = date.fromisoformat(last_date)
        except ValueError:
            return ""
        months_since = (today.year - last.year) * 12 + (today.month - last.month)
        if months_since >= interval.months:
            return f"{months_since} months since last (interval {interval.months} months)"

    return ""


def find_due(v: Vehicle, today: date) -> list[DueItem]:
    items: list[DueItem] = []

    for interval in for_make(v.make):
        reason = _service_due(v, interval, today)
        if reason:
            items.append(DueItem(
                item_id=f"service:{interval.name}",
                kind="service",
                title=interval.description,
                detail=reason,
            ))

    try:
        recalls = fetch_recalls(v.make, v.model, v.model_year or 0)
    except Exception as e:  # noqa: BLE001
        recalls = []
        print(f"<!-- recall fetch failed for {v.vin}: {e} -->", file=sys.stderr)
    for r in recalls:
        cid = r.get("NHTSACampaignNumber", "")
        if not cid or cid in v.acknowledged_recalls:
            continue
        s = summarize(r)
        items.append(DueItem(
            item_id=f"recall:{cid}",
            kind="recall",
            title=f"Recall {cid}: {s['component']}",
            detail=(s["consequence"] or "")[:300],
            booking_hint=(s["remedy"] or "")[:300],
        ))
    return items


# ----- Rendering -----------------------------------------------------------

def _vehicle_label(v: Vehicle) -> str:
    parts = [str(v.model_year or ""), v.make, v.model, v.trim]
    label = " ".join(p for p in parts if p).strip()
    return v.nickname or label or v.vin


def render_body(vehicles: list[Vehicle], today: date) -> str:
    lines = [f"# Car maintenance — last checked {today.isoformat()}", ""]
    for v in vehicles:
        lines.append(f"## {_vehicle_label(v)}")
        lines.append(f"- VIN: `{v.vin}`")
        if v.odometer is not None:
            proj = v.projected_odometer(today)
            note = f" (projected today: ~{proj:,} mi)" if proj and proj != v.odometer else ""
            lines.append(f"- Odometer: {v.odometer:,} mi as of {v.odometer_updated or 'unknown'}{note}")
        else:
            lines.append("- Odometer: **not logged yet** — `python -m car mileage <VIN> <miles>` or comment `mileage 12345` on this issue")

        # Active due items with nag state
        active_states = {s.item_id: s for s in v.due_state if not s.acknowledged_at}
        if active_states:
            lines.append("")
            lines.append("### Active alerts")
            for st in active_states.values():
                level, days = escalation_level(st, v.notification_policy, today)
                emoji = LEVEL_EMOJI[min(level, len(LEVEL_EMOJI) - 1)]
                tag = f"{emoji} " if emoji else ""
                lines.append(f"- {tag}`{st.item_id}` — first alerted {st.first_alerted_at} ({days} days), {st.alert_count} pings"
                             + (f", snoozed until {st.snoozed_until}" if st.snoozed_until else ""))
            lines.append("")
            lines.append("Reply to this issue with: `done <item_id>`, `snooze <item_id> 5d`, or `mileage 12345`.")
        else:
            lines.append("- All clear. Nice.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_today_comment(per_vehicle: dict[str, list[tuple[DueItem, int, int]]], today: date, vehicles: list[Vehicle]) -> tuple[str, int]:
    """Build today's nag comment. Returns (markdown, max_level_today)."""
    if not per_vehicle:
        return ("", 0)

    max_level = max(level for items in per_vehicle.values() for _, level, _ in items)
    emoji = LEVEL_EMOJI[min(max_level, len(LEVEL_EMOJI) - 1)]
    prefix = f"{emoji} " if emoji else ""

    headers = {
        0: f"Maintenance due — {today.isoformat()}",
        1: f"Still overdue — week 1 — {today.isoformat()}",
        2: f"**Two weeks overdue** — {today.isoformat()}",
        3: f"**THREE+ WEEKS OVERDUE** — {today.isoformat()}",
    }
    lines = [f"## {prefix}{headers[min(max_level, 3)]}", ""]

    by_vin = {v.vin: v for v in vehicles}
    for vin, items in per_vehicle.items():
        v = by_vin[vin]
        lines.append(f"**{_vehicle_label(v)}**")
        for item, level, days in items:
            tag = LEVEL_EMOJI[min(level, len(LEVEL_EMOJI) - 1)]
            tag = f"{tag} " if tag else ""
            day_note = "due today" if days == 0 else f"day {days}"
            lines.append(f"- {tag}**{item.title}** (`{item.item_id}`) — {day_note}. {item.detail}")
            if max_level >= 2 and item.booking_hint:
                lines.append(f"  - {item.booking_hint}")
            if max_level >= 3:
                url = (v.dealer or {}).get("scheduler_url", "")
                if url:
                    lines.append(f"  - **Book now:** {url}")
                else:
                    name = (v.dealer or {}).get("name", "your dealer")
                    lines.append(f"  - **Call {name} today.**")
        lines.append("")

    if max_level >= 1:
        lines.append("---")
        lines.append("Reply to silence: `done <item_id>` (handled it) · `snooze <item_id> 7d` · `ack <item_id>` (mute without booking).")
    return ("\n".join(lines).rstrip() + "\n", max_level)


# ----- Main pipeline -------------------------------------------------------

def run(today: date | None = None) -> tuple[str, str, int]:
    """Compute outputs without I/O. Returns (body_md, today_comment_md, max_level)."""
    today = today or date.today()
    vehicles = load_vehicles()
    if not vehicles:
        return ("No vehicles configured in data/vehicles.json\n", "", 0)

    if any(_hydrate(v) for v in vehicles):
        save_vehicles(vehicles)

    per_vehicle_today: dict[str, list[tuple[DueItem, int, int]]] = {}

    for v in vehicles:
        due = find_due(v, today)
        active_ids = {d.item_id for d in due}

        # Drop state for items that are no longer due (likely the user logged the service)
        v.due_state = [s for s in v.due_state if s.item_id in active_ids]

        for d in due:
            state = v.get_due_state(d.item_id)
            if state is None:
                state = DueState(item_id=d.item_id, first_alerted_at=today.isoformat())
                v.due_state.append(state)

            decision = decide(state, v.notification_policy, today)
            if decision.fire:
                state.last_alerted_at = today.isoformat()
                state.alert_count += 1
                per_vehicle_today.setdefault(v.vin, []).append((d, decision.level, decision.days_since_first_alert))

    save_vehicles(vehicles)

    body = render_body(vehicles, today)
    comment, max_level = render_today_comment(per_vehicle_today, today, vehicles)
    return (body, comment, max_level)


def main(argv: list[str] | None = None) -> int:
    body, comment, max_level = run()

    out_dir = Path(os.environ.get("CAR_OUT_DIR", "/tmp"))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.md").write_text(body)
    (out_dir / "today.md").write_text(comment)
    title_emoji = LEVEL_EMOJI[min(max_level, len(LEVEL_EMOJI) - 1)]
    title_label = LEVEL_LABEL[min(max_level, len(LEVEL_LABEL) - 1)]
    title = f"Car maintenance — {title_label}" if comment else "Car maintenance — all clear"
    if title_emoji:
        title = f"{title_emoji} {title}"
    (out_dir / "title.txt").write_text(title + "\n")

    # Echo to stdout so workflow logs are useful
    sys.stdout.write(body)
    if comment:
        sys.stdout.write("\n---\n")
        sys.stdout.write(comment)
    return 0


if __name__ == "__main__":
    sys.exit(main())
