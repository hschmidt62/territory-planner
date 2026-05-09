"""Look up open NHTSA recalls for a given make/model/year.

NHTSA's public recallsByVehicle endpoint returns campaigns at the model-year
level (no VIN-specific filtering on the free tier). We surface every campaign
and let the owner acknowledge them in vehicles.json.
"""
from __future__ import annotations

import urllib.request
import urllib.parse
import json

RECALLS_URL = (
    "https://api.nhtsa.gov/recalls/recallsByVehicle"
    "?make={make}&model={model}&modelYear={year}"
)


def fetch_recalls(make: str, model: str, model_year: int, timeout: float = 15.0) -> list[dict]:
    if not (make and model and model_year):
        return []
    url = RECALLS_URL.format(
        make=urllib.parse.quote(make),
        model=urllib.parse.quote(model),
        year=model_year,
    )
    req = urllib.request.Request(url, headers={"User-Agent": "territory-planner-car/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload.get("results", [])


def summarize(recall: dict) -> dict:
    """Pull just the fields we want to show in an alert."""
    return {
        "campaign_id": recall.get("NHTSACampaignNumber", ""),
        "component": recall.get("Component", ""),
        "summary": recall.get("Summary", ""),
        "consequence": recall.get("Consequence", ""),
        "remedy": recall.get("Remedy", ""),
        "report_received_date": recall.get("ReportReceivedDate", ""),
    }
