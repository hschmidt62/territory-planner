from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone

import click

from . import auth, calendar as cal, mail, organize
from .client import GraphClient


def _print_json(obj) -> None:
    click.echo(json.dumps(obj, indent=2, default=str))


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Outlook / Microsoft Graph CLI."""
    ctx.ensure_object(dict)
    ctx.obj["client"] = GraphClient()


@cli.command()
def login() -> None:
    """Sign in via device-code flow and cache the token."""
    auth.get_access_token()
    click.echo("Signed in. Token cached.", err=True)


@cli.command()
def logout() -> None:
    """Clear cached credentials."""
    n = auth.logout()
    click.echo(f"Removed {n} cached account(s).", err=True)


@cli.command()
@click.pass_context
def whoami(ctx: click.Context) -> None:
    """Show the signed-in user."""
    me = ctx.obj["client"].get("/me")
    _print_json({k: me.get(k) for k in ("displayName", "mail", "userPrincipalName", "id")})


# --- mail ---------------------------------------------------------------

@cli.group()
def email() -> None:
    """Mail commands."""


@email.command("list")
@click.option("--folder", default="inbox", help="Folder name or well-known id (inbox, drafts, sentitems, ...).")
@click.option("--top", default=25, show_default=True)
@click.option("--unread", is_flag=True, help="Only unread messages.")
@click.pass_context
def email_list(ctx: click.Context, folder: str, top: int, unread: bool) -> None:
    msgs = list(mail.list_messages(ctx.obj["client"], folder=folder, top=top, unread_only=unread))
    _print_json(msgs)


@email.command("search")
@click.argument("query")
@click.option("--top", default=25, show_default=True)
@click.pass_context
def email_search(ctx: click.Context, query: str, top: int) -> None:
    msgs = list(mail.search_messages(ctx.obj["client"], query, top=top))
    _print_json(msgs)


@email.command("folders")
@click.pass_context
def email_folders(ctx: click.Context) -> None:
    folders = list(mail.list_folders(ctx.obj["client"]))
    _print_json(folders)


@email.command("create-folder")
@click.argument("name")
@click.pass_context
def email_create_folder(ctx: click.Context, name: str) -> None:
    _print_json(mail.create_folder(ctx.obj["client"], name))


@email.command("move")
@click.argument("message_id")
@click.argument("folder_name")
@click.pass_context
def email_move(ctx: click.Context, message_id: str, folder_name: str) -> None:
    folder = mail.find_folder_by_name(ctx.obj["client"], folder_name)
    if not folder:
        raise click.ClickException(f"Folder not found: {folder_name}")
    _print_json(mail.move_message(ctx.obj["client"], message_id, folder["id"]))


@email.command("organize")
@click.option("--rules", "rules_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--limit", default=100, show_default=True, help="How many recent messages to scan.")
@click.option("--dry-run", is_flag=True, help="Print planned moves without applying them.")
@click.pass_context
def email_organize(ctx: click.Context, rules_path: str, limit: int, dry_run: bool) -> None:
    rules = organize.load_rules(rules_path)
    actions = organize.organize_inbox(ctx.obj["client"], rules, limit=limit, dry_run=dry_run)
    _print_json({"dry_run": dry_run, "count": len(actions), "actions": actions})


# --- calendar -----------------------------------------------------------

@cli.group()
def calendar() -> None:
    """Calendar commands."""


@calendar.command("list")
@click.option("--days", default=7, show_default=True, help="Window size starting now.")
@click.option("--top", default=50, show_default=True)
@click.pass_context
def calendar_list(ctx: click.Context, days: int, top: int) -> None:
    start = datetime.now(timezone.utc)
    end = start + timedelta(days=days)
    events = list(cal.list_events(ctx.obj["client"], start=start, end=end, top=top))
    _print_json(events)


@calendar.command("create")
@click.option("--subject", required=True)
@click.option("--start", "start_str", required=True, help="ISO 8601, e.g. 2026-05-09T15:00:00Z")
@click.option("--end", "end_str", required=True, help="ISO 8601")
@click.option("--body", default="")
@click.option("--location", default=None)
@click.option("--attendee", "attendees", multiple=True, help="Repeatable.")
@click.option("--tz", "timezone_name", default="UTC", show_default=True)
@click.pass_context
def calendar_create(
    ctx: click.Context,
    subject: str,
    start_str: str,
    end_str: str,
    body: str,
    location: str | None,
    attendees: tuple[str, ...],
    timezone_name: str,
) -> None:
    start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
    end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
    event = cal.create_event(
        ctx.obj["client"],
        subject=subject,
        start=start,
        end=end,
        body=body,
        location=location,
        attendees=list(attendees) or None,
        timezone_name=timezone_name,
    )
    _print_json(event)


def main() -> None:
    try:
        cli(obj={})
    except Exception as exc:  # noqa: BLE001
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
