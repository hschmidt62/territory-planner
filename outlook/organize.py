from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .client import GraphClient
from .mail import ensure_folder, list_messages, move_message


@dataclass(frozen=True)
class Rule:
    """A single inbox rule. The first matching rule wins."""

    name: str
    folder: str
    from_contains: tuple[str, ...] = ()
    subject_contains: tuple[str, ...] = ()
    subject_regex: str | None = None

    def matches(self, message: dict[str, Any]) -> bool:
        sender = ((message.get("from") or {}).get("emailAddress") or {}).get("address", "").lower()
        subject = (message.get("subject") or "").lower()

        if self.from_contains and not any(s.lower() in sender for s in self.from_contains):
            return False
        if self.subject_contains and not any(s.lower() in subject for s in self.subject_contains):
            return False
        if self.subject_regex and not re.search(self.subject_regex, subject, re.IGNORECASE):
            return False
        # Require at least one positive condition.
        return bool(self.from_contains or self.subject_contains or self.subject_regex)


def load_rules(path: str | Path) -> list[Rule]:
    data = json.loads(Path(path).read_text())
    rules: list[Rule] = []
    for entry in data:
        rules.append(
            Rule(
                name=entry["name"],
                folder=entry["folder"],
                from_contains=tuple(entry.get("from_contains", ())),
                subject_contains=tuple(entry.get("subject_contains", ())),
                subject_regex=entry.get("subject_regex"),
            )
        )
    return rules


def organize_inbox(
    client: GraphClient,
    rules: list[Rule],
    *,
    limit: int = 100,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Apply rules to recent inbox messages. Returns a list of move actions taken."""
    folder_ids: dict[str, str] = {}
    actions: list[dict[str, Any]] = []

    for message in list_messages(client, folder="inbox", top=limit):
        for rule in rules:
            if not rule.matches(message):
                continue
            action = {
                "message_id": message["id"],
                "subject": message.get("subject"),
                "from": ((message.get("from") or {}).get("emailAddress") or {}).get("address"),
                "rule": rule.name,
                "destination": rule.folder,
                "applied": False,
            }
            if not dry_run:
                if rule.folder not in folder_ids:
                    folder_ids[rule.folder] = ensure_folder(client, rule.folder)["id"]
                move_message(client, message["id"], folder_ids[rule.folder])
                action["applied"] = True
            actions.append(action)
            break  # first matching rule wins

    return actions
