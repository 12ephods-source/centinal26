import datetime as dt
import sqlite3

from frost_core.p05_prospective import (
    candidate_probability,
    completed_baseline_days,
    has_rain,
    issue,
    resolve_due,
    score,
    verify_audit,
)


def fixture(target):
    forecast = {"hourly": {"time": [], "precipitation_probability": []}}
    for hour in range(24):
        forecast["hourly"]["time"].append(f"{target}T{hour:02d}:00")
        forecast["hourly"]["precipitation_probability"].append(
            70 if hour == 18 else 10
        )

    rows = []
    timezone = dt.timezone(dt.timedelta(hours=-6))

    def add_day(day, rain):
        for hour in range(24):
            raw = f"MMMX {hour:02d}0000Z 00000KT 10SM FEW020 20/10 A3000"
            if rain and hour == 17:
                raw = f"MMMX {hour:02d}0000Z 00000KT 5SM -RA BKN020 20/10 A3000"
            observed = dt.datetime.combine(day, dt.time(hour), timezone).astimezone(
                dt.timezone.utc
            )
            rows.append({"rawOb": raw, "obsTime": observed.isoformat()})

    for index in range(15, 1, -1):
        add_day(target - dt.timedelta(days=index), index % 3 == 0)
    return forecast, rows, add_day


def test_prospective_cycle(tmp_path):
    timezone = dt.timezone(dt.timedelta(hours=-6))
    target = dt.datetime.now(timezone).date() + dt.timedelta(days=1)
    forecast, rows, add_day = fixture(target)

    baseline_days = completed_baseline_days(target)
    assert len(baseline_days) == 14
    assert baseline_days[0] == target - dt.timedelta(days=15)
    assert baseline_days[-1] == target - dt.timedelta(days=2)
    assert target - dt.timedelta(days=1) not in baseline_days

    assert candidate_probability(forecast, target) == 0.70
    assert has_rain({"rawOb": "MMMX 181800Z 5SM -RA BKN020"})

    db = tmp_path / "p05.sqlite3"
    first = issue(db, target, forecast, rows)
    assert first["gate"] == "EXPERIMENTAL"
    assert issue(db, target, forecast, rows)["status"] == "NOOP_DUPLICATE"

    add_day(target, True)
    resolution = resolve_due(db, rows, today=target + dt.timedelta(days=1))
    assert resolution["resolved"][0]["outcome"] == 1
    assert score(db)["resolved"] == 1
    assert verify_audit(db)["status"] == "PASS"

    con = sqlite3.connect(db)
    try:
        con.execute("UPDATE forecasts SET probability=.1")
        con.commit()
        raise AssertionError("forecast immutability trigger failed")
    except sqlite3.DatabaseError:
        pass
    finally:
        con.close()
