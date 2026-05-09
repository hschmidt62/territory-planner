"""Decode a VIN via NHTSA's free vPIC API."""
from __future__ import annotations

import urllib.request
import urllib.parse
import json

VPIC_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/decodevinvalues/{vin}?format=json"


def decode_vin(vin: str, timeout: float = 15.0) -> dict[str, str]:
    """Return a dict with at least: make, model, model_year, trim, body_class.

    Raises urllib.error.URLError on network failure.
    """
    url = VPIC_URL.format(vin=urllib.parse.quote(vin))
    req = urllib.request.Request(url, headers={"User-Agent": "territory-planner-car/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    r = payload["Results"][0]

    def pick(*keys: str) -> str:
        for k in keys:
            v = r.get(k)
            if v:
                return str(v)
        return ""

    year = pick("ModelYear")
    return {
        "make": pick("Make").title(),
        "model": pick("Model"),
        "model_year": int(year) if year.isdigit() else "",
        "trim": pick("Trim", "Trim2", "Series"),
        "body_class": pick("BodyClass"),
        "engine_l": pick("DisplacementL"),
        "fuel": pick("FuelTypePrimary"),
        "plant_city": pick("PlantCity"),
    }
