# P05 Prospective Intelligence Awareness

This integration adds a narrow, prospective forecasting lane to Frost CORE without creating another executor or source of authority.

## Invariant

`forecasting != authorization != execution != verification`

The module records and scores prospective forecasts. It does not grant Guardian authority, claim device jobs, merge code, or promote unrelated models.

## Cohort

`MMMX_NEXTDAY_REPORTED_RAIN_V1`

Candidate source: Open-Meteo next-day hourly precipitation probability.

Resolution source: NOAA/NWS Aviation Weather Center METAR observations for MMMX.

Event: TRUE iff at least one MMMX METAR observation on the target local calendar day contains a present-weather RA or DZ token. A negative requires at least 12 reports spanning at least 10 distinct local hours.

Baseline: Beta(1,1)-smoothed wet-day frequency from the previous 14 usable MMMX METAR days.

## Epistemic policy

New forecasts remain `EXPERIMENTAL` until prospective evidence is sufficient. Synthetic and backtest results do not count toward real-world competence.

The current minimum resolved sample is 100. Passing that count alone is not a promotion; calibration and positive baseline-relative skill still require independent qualification.

## Data integrity

Forecasts, resolutions, and audit events are append-only. Audit events are SHA-256 hash chained. Duplicate target issuance is idempotently rejected.

## Scientific boundary

This benchmark measures predictive performance for one preregistered METAR-defined event. It does not establish general intelligence, consciousness, universal forecasting ability, or competence outside this domain/horizon.
