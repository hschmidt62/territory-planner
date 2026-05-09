# Car maintenance reminder

A daily GitHub Action that watches the cars in `../data/vehicles.json` and opens a GitHub Issue when:

- An NHTSA recall is open for the vehicle
- A service interval (oil, tires, filters, brake fluid, etc.) is due based on logged mileage and dates

This is **Phase 1**. It uses no paid services — alerts arrive via the GitHub mobile app's notifications. Phase 2 swaps the GitHub Issue for a Telegram bot with one-tap booking links to your dealer's online scheduler.

## Adding a vehicle

Edit `data/vehicles.json`. Only `vin` and `dealer.name` are required to start. The workflow will fill in `make`, `model`, and `trim` from NHTSA's free VIN decoder on its first run.

```json
{
  "vin": "4S4GUHF6XS3713787",
  "model_year": 2025,
  "odometer": 1234,
  "odometer_updated": "2026-05-09",
  "dealer": { "name": "Georgetown Subaru" }
}
```

## Logging mileage / services from the CLI

```bash
pip install click
python -m car list
python -m car mileage 4S4GUHF6XS3713787 4500
python -m car logged 4S4GUHF6XS3713787 oil_and_filter 4500 --on 2026-05-09
python -m car check          # prints the same report the workflow generates
```

You don't need the CLI — editing `data/vehicles.json` directly works too. The CLI just keeps you from typoing the VIN.

## Service interval source

`intervals.py` ships Subaru's normal-duty schedule (2024–2025 booklet). Severe-duty (towing, off-road, very dusty/cold) shortens oil & rotation to ~3,750 mi — adjust the table if that applies. Other makes fall back to a generic 5,000-mile-oil schedule until per-make tables are added.

## How alerts work

The workflow runs daily at 13:00 UTC (configurable). It edits a single rolling Issue labeled `car-maintenance` so your notification list doesn't fill up. When nothing is due, it stays quiet.
