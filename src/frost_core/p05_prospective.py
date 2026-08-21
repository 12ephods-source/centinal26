from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sqlite3
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Mexico_City")
RAIN_RE = re.compile(r"(?<![A-Z])[-+]?(?:SH|TS|FZ|VC)?(?:RA|DZ)(?![A-Z])")
OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
AWC_METAR = "https://aviationweather.gov/api/data/metar"
UA = "Frost-P05/1.0 (+prospective-validation)"

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS forecasts(
  forecast_id TEXT PRIMARY KEY,
  cohort_id TEXT NOT NULL,
  issued_at TEXT NOT NULL,
  target_date TEXT NOT NULL,
  evidence_cutoff TEXT NOT NULL,
  probability REAL NOT NULL CHECK(probability BETWEEN 0 AND 1),
  baseline_probability REAL NOT NULL CHECK(baseline_probability BETWEEN 0 AND 1),
  gate TEXT NOT NULL CHECK(gate IN ('PASS','EXPERIMENTAL','BLOCK')),
  model TEXT NOT NULL,
  resolution_source TEXT NOT NULL,
  evidence_hash TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS resolutions(
  forecast_id TEXT PRIMARY KEY REFERENCES forecasts(forecast_id),
  resolved_at TEXT NOT NULL,
  outcome INTEGER NOT NULL CHECK(outcome IN (0,1)),
  source_hash TEXT NOT NULL,
  coverage_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit(
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  event_time TEXT NOT NULL,
  event_type TEXT NOT NULL,
  forecast_id TEXT,
  payload_json TEXT NOT NULL,
  prev_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL UNIQUE
);
CREATE TRIGGER IF NOT EXISTS forecasts_no_update BEFORE UPDATE ON forecasts BEGIN
 SELECT RAISE(ABORT,'forecasts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS forecasts_no_delete BEFORE DELETE ON forecasts BEGIN
 SELECT RAISE(ABORT,'forecasts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS resolutions_no_update BEFORE UPDATE ON resolutions BEGIN
 SELECT RAISE(ABORT,'resolutions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS resolutions_no_delete BEFORE DELETE ON resolutions BEGIN
 SELECT RAISE(ABORT,'resolutions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit BEGIN
 SELECT RAISE(ABORT,'audit is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN
 SELECT RAISE(ABORT,'audit is append-only'); END;
"""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(value: Any) -> str:
    raw = value if isinstance(value, str) else canonical(value)
    return hashlib.sha256(raw.encode()).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def connect(path: str | Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def _append_audit(
    con: sqlite3.Connection,
    event_type: str,
    forecast_id: str | None,
    payload: dict,
) -> None:
    prev = con.execute("SELECT event_hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
    prev_hash = prev[0] if prev else "0" * 64
    body = {
        "event_time": utc_now(),
        "event_type": event_type,
        "forecast_id": forecast_id,
        "payload": payload,
        "prev_hash": prev_hash,
    }
    event_hash = sha(body)
    con.execute(
        "INSERT INTO audit(event_time,event_type,forecast_id,payload_json,prev_hash,event_hash) VALUES(?,?,?,?,?,?)",
        (
            body["event_time"],
            event_type,
            forecast_id,
            canonical(payload),
            prev_hash,
            event_hash,
        ),
    )


def verify_audit(path: str | Path) -> dict:
    con = connect(path)
    rows = con.execute("SELECT * FROM audit ORDER BY seq").fetchall()
    con.close()
    prev = "0" * 64
    for row in rows:
        if row["prev_hash"] != prev:
            return {"status": "FAIL", "seq": row["seq"], "reason": "prev_hash"}
        body = {
            "event_time": row["event_time"],
            "event_type": row["event_type"],
            "forecast_id": row["forecast_id"],
            "payload": json.loads(row["payload_json"]),
            "prev_hash": row["prev_hash"],
        }
        if sha(body) != row["event_hash"]:
            return {"status": "FAIL", "seq": row["seq"], "reason": "event_hash"}
        prev = row["event_hash"]
    return {"status": "PASS", "events": len(rows), "tip": prev}


@dataclass(frozen=True)
class MMMXCohort:
    cohort_id: str = "MMMX_NEXTDAY_REPORTED_RAIN_V1"
    station: str = "MMMX"
    latitude: float = 19.4363
    longitude: float = -99.0721
    model: str = "openmeteo_max_hour_pop_v1"
    resolution_source: str = "NOAA/NWS Aviation Weather Center METAR Data API"
    minimum_resolved: int = 100

    def event_text(self, target: dt.date) -> str:
        return (
            f"TRUE iff at least one {self.station} METAR observation on {target} local date "
            "contains a present-weather RA or DZ token; negative requires >=12 reports "
            "covering >=10 distinct local hours."
        )


def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        if response.status == 204:
            return []
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {url}")
        return json.loads(response.read().decode())


def fetch_open_meteo(cohort: MMMXCohort) -> dict:
    query = urllib.parse.urlencode(
        {
            "latitude": cohort.latitude,
            "longitude": cohort.longitude,
            "hourly": "precipitation_probability",
            "timezone": "America/Mexico_City",
            "forecast_days": 3,
        }
    )
    return _get_json(f"{OPEN_METEO}?{query}")


def fetch_metars(cohort: MMMXCohort, hours: int = 360) -> list[dict]:
    query = urllib.parse.urlencode(
        {"ids": cohort.station, "format": "json", "hours": hours}
    )
    data = _get_json(f"{AWC_METAR}?{query}")
    if not isinstance(data, list):
        raise RuntimeError("AWC response was not a JSON list")
    return data


def _obs_time(row: dict) -> dt.datetime | None:
    for key in ("obsTime", "observation_time", "reportTime", "issueTime"):
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, (int, float)) or str(value).isdigit():
            try:
                return dt.datetime.fromtimestamp(float(value), dt.timezone.utc)
            except (ValueError, OSError):
                continue
        try:
            return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(
                dt.timezone.utc
            )
        except ValueError:
            continue
    return None


def _raw(row: dict) -> str:
    for key in ("rawOb", "raw_text", "rawText", "raw", "wxString", "wx"):
        if row.get(key):
            return str(row[key]).upper()
    return ""


def has_rain(row: dict) -> bool:
    return bool(RAIN_RE.search(_raw(row)))


def rows_for_day(rows: list[dict], day: dt.date) -> list[dict]:
    return [
        row
        for row in rows
        if (observed := _obs_time(row)) is not None
        and observed.astimezone(TZ).date() == day
    ]


def resolve_day(rows: list[dict], day: dt.date) -> tuple[int | None, dict]:
    day_rows = rows_for_day(rows, day)
    times = sorted(
        observed.astimezone(TZ)
        for row in day_rows
        if (observed := _obs_time(row)) is not None
    )
    if not times:
        return None, {"status": "NO_DATA", "reports": 0}
    hours = {value.hour for value in times}
    meta = {
        "reports": len(day_rows),
        "unique_hours": len(hours),
        "first": times[0].isoformat(),
        "last": times[-1].isoformat(),
    }
    if any(has_rain(row) for row in day_rows):
        return 1, {"status": "POSITIVE", **meta}
    if len(day_rows) < 12 or len(hours) < 10:
        return None, {"status": "INSUFFICIENT_COVERAGE", **meta}
    return 0, {"status": "NEGATIVE", **meta}


def candidate_probability(data: dict, target: dt.date) -> float:
    hourly = data.get("hourly") or {}
    values = []
    for stamp, probability in zip(
        hourly.get("time") or [], hourly.get("precipitation_probability") or []
    ):
        try:
            if (
                dt.datetime.fromisoformat(str(stamp)).date() == target
                and probability is not None
            ):
                values.append(float(probability) / 100.0)
        except ValueError:
            pass
    if not values:
        raise RuntimeError(f"no Open-Meteo probability for {target}")
    return max(values)


def baseline_probability(
    rows: list[dict], target: dt.date, days: int = 14
) -> tuple[float, dict]:
    outcomes = []
    for index in range(days, 0, -1):
        outcome, _ = resolve_day(rows, target - dt.timedelta(days=index))
        if outcome is not None:
            outcomes.append(outcome)
    wet = sum(outcomes)
    count = len(outcomes)
    return (wet + 1) / (count + 2), {
        "usable_days": count,
        "wet_days": wet,
        "smoothing": "Beta(1,1)",
    }


def issue(
    path: str | Path,
    target: dt.date,
    forecast_data: dict,
    metars: list[dict],
    cohort: MMMXCohort = MMMXCohort(),
) -> dict:
    if target <= dt.datetime.now(TZ).date():
        raise ValueError("target must be prospective")
    con = connect(path)
    existing = con.execute(
        "SELECT forecast_id FROM forecasts WHERE cohort_id=? AND target_date=?",
        (cohort.cohort_id, str(target)),
    ).fetchone()
    if existing:
        con.close()
        return {"status": "NOOP_DUPLICATE", "forecast_id": existing[0]}
    probability = candidate_probability(forecast_data, target)
    baseline, baseline_meta = baseline_probability(metars, target)
    issued = utc_now()
    evidence_hash = sha({"forecast": forecast_data, "baseline_metars": metars})
    gate = "EXPERIMENTAL"
    forecast_id = f"P05-{uuid.uuid4().hex[:12].upper()}"
    con.execute(
        "INSERT INTO forecasts VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            forecast_id,
            cohort.cohort_id,
            issued,
            str(target),
            issued,
            probability,
            baseline,
            gate,
            cohort.model,
            cohort.resolution_source,
            evidence_hash,
            "prospective-only; synthetic/backtest evidence cannot promote competence",
        ),
    )
    _append_audit(
        con,
        "FORECAST_ISSUED",
        forecast_id,
        {
            "target": str(target),
            "p": probability,
            "baseline": baseline,
            "gate": gate,
            "baseline_meta": baseline_meta,
        },
    )
    con.commit()
    con.close()
    return {
        "status": "ISSUED",
        "forecast_id": forecast_id,
        "target": str(target),
        "probability": probability,
        "baseline_probability": baseline,
        "gate": gate,
    }


def resolve_due(
    path: str | Path,
    metars: list[dict],
    today: dt.date | None = None,
    cohort: MMMXCohort = MMMXCohort(),
) -> dict:
    today = today or dt.datetime.now(TZ).date()
    con = connect(path)
    rows = con.execute(
        "SELECT f.* FROM forecasts f LEFT JOIN resolutions r USING(forecast_id) "
        "WHERE f.cohort_id=? AND r.forecast_id IS NULL ORDER BY target_date",
        (cohort.cohort_id,),
    ).fetchall()
    resolved = []
    pending = []
    source_hash = sha(metars)
    for row in rows:
        target = dt.date.fromisoformat(row["target_date"])
        if target >= today:
            continue
        outcome, coverage = resolve_day(metars, target)
        if outcome is None:
            pending.append(
                {
                    "forecast_id": row["forecast_id"],
                    "target": str(target),
                    "coverage": coverage,
                }
            )
            continue
        con.execute(
            "INSERT INTO resolutions VALUES(?,?,?,?,?)",
            (row["forecast_id"], utc_now(), outcome, source_hash, canonical(coverage)),
        )
        _append_audit(
            con,
            "FORECAST_RESOLVED",
            row["forecast_id"],
            {"outcome": outcome, "source_hash": source_hash, "coverage": coverage},
        )
        resolved.append(
            {
                "forecast_id": row["forecast_id"],
                "target": str(target),
                "outcome": outcome,
            }
        )
    con.commit()
    con.close()
    return {"resolved": resolved, "pending": pending}


def score(path: str | Path, cohort: MMMXCohort = MMMXCohort()) -> dict:
    con = connect(path)
    rows = con.execute(
        "SELECT f.probability,f.baseline_probability,r.outcome FROM forecasts f "
        "JOIN resolutions r USING(forecast_id) WHERE f.cohort_id=?",
        (cohort.cohort_id,),
    ).fetchall()
    con.close()
    resolved = len(rows)
    if not resolved:
        return {"resolved": 0, "competence": "INSUFFICIENT", "gate": "EXPERIMENTAL"}
    model_brier = sum((row["probability"] - row["outcome"]) ** 2 for row in rows) / resolved
    baseline_brier = (
        sum((row["baseline_probability"] - row["outcome"]) ** 2 for row in rows)
        / resolved
    )
    skill = None if baseline_brier == 0 else 1 - model_brier / baseline_brier
    if resolved < cohort.minimum_resolved:
        competence = "INSUFFICIENT"
    elif skill is None or skill <= 0:
        competence = "REVIEW"
    else:
        competence = "CANDIDATE"
    return {
        "resolved": resolved,
        "brier": model_brier,
        "baseline_brier": baseline_brier,
        "brier_skill": skill,
        "competence": competence,
        "gate": "REVIEW" if competence == "CANDIDATE" else "EXPERIMENTAL",
    }


def cycle(
    path: str | Path,
    target: dt.date | None = None,
    cohort: MMMXCohort = MMMXCohort(),
) -> dict:
    today = dt.datetime.now(TZ).date()
    target = target or (today + dt.timedelta(days=1))
    metars = fetch_metars(cohort)
    resolved = resolve_due(path, metars, today=today, cohort=cohort)
    forecast = fetch_open_meteo(cohort)
    issued = issue(path, target, forecast, metars, cohort)
    return {
        "resolved": resolved,
        "issued": issued,
        "score": score(path, cohort),
        "audit": verify_audit(path),
    }
