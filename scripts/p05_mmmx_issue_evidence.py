from __future__ import annotations

import datetime as dt
import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

from frost_core.p05_prospective import MMMXCohort, baseline_probability, candidate_probability, canonical

TARGET = dt.date(2026, 8, 22)
UA = "Frost-P05/1.0 (+prospective-validation)"
OUT = Path("artifacts/p05-mmmx-20260822")
OUT.mkdir(parents=True, exist_ok=True)
cohort = MMMXCohort()


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {url}")
        return response.read()


openmeteo_url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(
    {
        "latitude": cohort.latitude,
        "longitude": cohort.longitude,
        "hourly": "precipitation_probability",
        "timezone": "America/Mexico_City",
        "forecast_days": 3,
    }
)
awc_url = "https://aviationweather.gov/api/data/metar?" + urllib.parse.urlencode(
    {"ids": cohort.station, "format": "json", "hours": 360}
)

openmeteo_raw = fetch_bytes(openmeteo_url)
awc_raw = fetch_bytes(awc_url)
(OUT / "openmeteo.json").write_bytes(openmeteo_raw)
(OUT / "awc_mmmx_metars.json").write_bytes(awc_raw)

forecast_data = json.loads(openmeteo_raw.decode())
metars = json.loads(awc_raw.decode())
if not isinstance(metars, list):
    raise RuntimeError("AWC response is not a JSON list")

p = candidate_probability(forecast_data, TARGET)
baseline, meta = baseline_probability(metars, TARGET)
evidence_hash = hashlib.sha256(
    canonical({"forecast": forecast_data, "baseline_metars": metars}).encode()
).hexdigest()
result = {
    "cohort_id": cohort.cohort_id,
    "target": str(TARGET),
    "candidate_model": cohort.model,
    "resolution_source": cohort.resolution_source,
    "event_definition": cohort.event_text(TARGET),
    "candidate_probability": p,
    "baseline_probability": baseline,
    "baseline_meta": meta,
    "gate": "EXPERIMENTAL",
    "openmeteo_url": openmeteo_url,
    "awc_url": awc_url,
    "openmeteo_raw_sha256": hashlib.sha256(openmeteo_raw).hexdigest(),
    "awc_raw_sha256": hashlib.sha256(awc_raw).hexdigest(),
    "evidence_hash": evidence_hash,
    "acquired_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
}
(OUT / "issuance.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
with (OUT / "SHA256SUMS.txt").open("w") as handle:
    for name in ("openmeteo.json", "awc_mmmx_metars.json", "issuance.json"):
        raw = (OUT / name).read_bytes()
        handle.write(f"{hashlib.sha256(raw).hexdigest()}  {name}\n")
print(json.dumps(result, sort_keys=True))
