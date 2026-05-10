"""Local CLI: log mileage, log a service, run a check."""
from __future__ import annotations

import sys
from datetime import date

import click

from .store import Vehicle, ServiceLogEntry, load_vehicles, save_vehicles
from .check import main as check_main


def _find(vehicles: list[Vehicle], vin_or_nick: str) -> Vehicle:
    needle = vin_or_nick.lower()
    for v in vehicles:
        if v.vin.lower() == needle or v.nickname.lower() == needle:
            return v
    raise click.ClickException(f"No vehicle matching '{vin_or_nick}'")


@click.group()
def cli() -> None:
    """Manage vehicles in data/vehicles.json."""


@cli.command("list")
def list_cmd() -> None:
    """List configured vehicles."""
    for v in load_vehicles():
        title = " ".join(p for p in (str(v.model_year or ""), v.make, v.model) if p) or "(undecoded)"
        odo = f"{v.odometer:,} mi" if v.odometer is not None else "no odometer logged"
        click.echo(f"{v.vin}  {v.nickname or title}  ({odo})")


@cli.command("mileage")
@click.argument("vin_or_nickname")
@click.argument("miles", type=int)
@click.option("--on", default=None, help="YYYY-MM-DD; defaults to today")
def mileage_cmd(vin_or_nickname: str, miles: int, on: str | None) -> None:
    """Update the current odometer reading."""
    vehicles = load_vehicles()
    v = _find(vehicles, vin_or_nickname)
    when = on or date.today().isoformat()
    if v.odometer is not None and miles < v.odometer:
        raise click.ClickException(
            f"New mileage {miles:,} is lower than recorded {v.odometer:,}; refusing."
        )
    v.odometer = miles
    v.odometer_updated = when
    save_vehicles(vehicles)
    click.echo(f"Updated {v.vin}: {miles:,} mi as of {when}")


@cli.command("logged")
@click.argument("vin_or_nickname")
@click.argument("service")
@click.argument("miles", type=int)
@click.option("--on", default=None, help="YYYY-MM-DD; defaults to today")
@click.option("--notes", default="")
def logged_cmd(vin_or_nickname: str, service: str, miles: int, on: str | None, notes: str) -> None:
    """Record that a service was performed (e.g. `oil_and_filter`)."""
    vehicles = load_vehicles()
    v = _find(vehicles, vin_or_nickname)
    when = on or date.today().isoformat()
    v.service_log.append(ServiceLogEntry(date=when, odometer=miles, service=service, notes=notes))
    # Also bump the odometer if this is the latest reading.
    if v.odometer is None or miles > v.odometer:
        v.odometer = miles
        v.odometer_updated = when
    save_vehicles(vehicles)
    click.echo(f"Logged {service} on {when} at {miles:,} mi for {v.vin}")


@cli.command("check")
def check_cmd() -> None:
    """Run the same check the daily workflow runs."""
    sys.exit(check_main())


if __name__ == "__main__":
    cli()
