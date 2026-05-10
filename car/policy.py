"""Nag-scheduling logic.

Decides, for each currently-due item, whether to fire an alert today and at
what escalation level. Pure functions so they're easy to test.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .store import DueState, NotificationPolicy


@dataclass
class AlertDecision:
    fire: bool
    level: int                   # 0..len(policy.escalation_days)
    days_since_first_alert: int
    reason: str = ""             # why fire/skip


LEVEL_LABEL = ["due", "overdue 1 week", "overdue 2 weeks", "overdue 3 weeks+"]
LEVEL_EMOJI = ["", "⚠️", "🔴", "🚨"]


def _parse(d: str) -> date | None:
    if not d:
        return None
    try:
        return date.fromisoformat(d)
    except ValueError:
        return None


def escalation_level(state: DueState, policy: NotificationPolicy, today: date) -> tuple[int, int]:
    """Return (level, days_since_first_alert)."""
    first = _parse(state.first_alerted_at) or today
    days = max(0, (today - first).days)
    level = 0
    for i, threshold in enumerate(policy.escalation_days, start=1):
        if days >= threshold:
            level = i
    return level, days


def decide(state: DueState, policy: NotificationPolicy, today: date) -> AlertDecision:
    if not policy.enabled:
        return AlertDecision(False, 0, 0, "policy disabled")

    if state.acknowledged_at:
        return AlertDecision(False, 0, 0, f"acknowledged on {state.acknowledged_at}")

    snoozed = _parse(state.snoozed_until)
    if snoozed and today < snoozed:
        return AlertDecision(False, 0, 0, f"snoozed until {state.snoozed_until}")

    level, days_since = escalation_level(state, policy, today)
    freq = policy.frequency_by_level[min(level, len(policy.frequency_by_level) - 1)]

    last = _parse(state.last_alerted_at)
    if last is None:
        return AlertDecision(True, level, days_since, "first alert")

    if (today - last) >= timedelta(days=freq):
        return AlertDecision(True, level, days_since, f"{(today - last).days} days since last alert (freq {freq})")

    return AlertDecision(False, level, days_since, f"only {(today - last).days} days since last alert (freq {freq})")
