# Car maintenance reminder

A daily GitHub Action that watches the cars in `../data/vehicles.json` and pings you on a single rolling GitHub Issue when:

- An open NHTSA recall is found for the make / model / year, or
- A service interval (oil, tires, filters, brake fluid, etc.) is due

Every day with active alerts, the workflow posts a fresh comment on the rolling issue so the GitHub mobile app fires a phone notification. Alerts **escalate** the longer they go unacknowledged.

## Adding a vehicle

Edit `data/vehicles.json`. Only `vin` and `dealer.name` are required to start. The workflow's first run hits NHTSA's free vPIC API and fills in `make`, `model`, `trim`.

```json
{
  "vin": "4S4GUHF6XS3713787",
  "model_year": 2025,
  "odometer": 1234,
  "odometer_updated": "2026-05-09",
  "dealer": { "name": "Georgetown Subaru", "scheduler_url": "" }
}
```

## Nag policy

Default policy: **daily after due, escalates at week 1 / 2 / 3.** Override per-vehicle:

```json
"notification_policy": {
  "enabled": true,
  "escalation_days": [7, 14, 21],
  "frequency_by_level": [1, 1, 1, 1]
}
```

`frequency_by_level[i]` = days between alerts at escalation level i. `[7, 7, 1, 1]` means weekly until day 14, then daily.

| Level | Trigger              | Severity                                      |
|-------|----------------------|-----------------------------------------------|
| 0     | day 0 to escalation_days[0]  | Plain alert                            |
| 1     | escalation_days[0]+  | ⚠️ "Still overdue"                            |
| 2     | escalation_days[1]+  | 🔴 "Two weeks overdue" + recall remedies      |
| 3     | escalation_days[2]+  | 🚨 "THREE+ WEEKS OVERDUE" + booking URL        |

Set `"enabled": false` to disable nagging entirely (you'll still get the first alert when something becomes due).

## Replying from your phone

Reply to the rolling Issue with any of these (case-insensitive, item_ids are shown in the alert):

```
done service:oil_and_filter            # I got it done; clears the alert
done service:oil_and_filter at 18100   # also logs the service at that mileage
ack service:oil_and_filter             # silence without claiming it's done
snooze service:oil_and_filter 5d       # 5 days; '1w' / '2w' also work
unsnooze service:oil_and_filter        # cancel snooze
mileage 18100                          # update odometer (today's date)
mileage 18100 on 2026-05-09            # ...or a past date
```

Multiple commands per comment are fine, one per line. The bot replies with what it applied and commits the update to `data/vehicles.json`.

Only the repo owner's comments are honored — other commenters are ignored by the ack workflow.

## CLI for local edits

```bash
pip install click
python -m car list
python -m car mileage 4S4GUHF6XS3713787 4500
python -m car logged 4S4GUHF6XS3713787 oil_and_filter 4500 --on 2026-05-09
python -m car check                      # prints the daily report
echo "snooze service:oil_and_filter 1w" | python -m car.ack
```

## Service interval source

`intervals.py` ships Subaru's normal-duty schedule (2024–2025 booklet). If you tow, off-road, or live in extreme conditions, shorten oil & rotation to ~3,750 mi. Other makes use a generic 5,000-mile-oil schedule until per-make tables are added.

## How alerts work

Cron at 13:00 UTC (configurable in `.github/workflows/car-check.yml`). The workflow:

1. Decodes any unhydrated VIN via NHTSA, commits the update.
2. Computes due items + nag decisions, persists `due_state` to `data/vehicles.json`.
3. Updates the rolling Issue's title + body to reflect current state.
4. If anything is due today, posts a fresh comment so your phone pings.

When everything is clear, the workflow stays quiet (no comment posted, title shows "all clear").

## What's not built yet

- **Phase 3: online booking via Playwright + Xtime.** When you share Georgetown Subaru's "Schedule Service" URL, the bot will scrape available slots and book directly — no phone call, no Twilio, no AI calling fees.
- **Telegram bot front-end.** Same nag, but with one-tap reply buttons instead of typing commands.
