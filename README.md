# Automation OS — Centinal26

Canonical implementation repository for Robert Frost's Automation project.

## Core invariant

Every consequential operation follows:

`Intent → Authorization → Event/Queue → Capability Selection → Bounded Execution → Verification → Evidence/Audit → State Update → Controlled Evolution`

No module may bypass authorization, bounded execution, verification, or audit to gain convenience or autonomy.

## Working baseline

The repository now contains a runnable Python 3.11+ core:

- explicit, expiring capability grants
- registered capability allowlist; no arbitrary shell execution
- durable SQLite job queue and state transitions
- append-only SHA-256 hash-linked audit records
- CLI initialization, demonstration, worker step, and status commands
- pytest invariant tests and Ruff linting
- CI across Python 3.11, 3.12, and 3.13
- Termux installation/bootstrap script

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
centinal26 init
centinal26 demo
centinal26 status
pytest
```

Termux:

```bash
bash scripts/install-termux.sh
```

State defaults to `~/.local/state/centinal26`; set `CENTINAL26_HOME` to override it.

## Repository role

GitHub is the durable engineering source of truth: code, deployment assets,
tests, schemas, CI, release manifests, and history. Device-side execution
remains in Termux/Hermes/local workers; GitHub does not itself execute Android
commands.

## Layout

- `src/centinal26/` — runnable orchestration core and CLI
- `workers/` — bounded workers and job consumers
- `deploy/termux/`, `scripts/` — Android/Termux deployment
- `schemas/` — job, evidence, audit, capability, and release schemas
- `tests/` — invariant, schema, and runtime validation
- `docs/` — architecture, threat model, operating model, provenance
- `.github/workflows/` — automated validation
- `releases/` — release manifests and validation state

## Subsystem status taxonomy

Every imported or evolved subsystem must be classified as one of
`CANONICAL`, `COMPATIBLE_MODULE`, `EXPERIMENTAL`, `SUPERSEDED`, or
`REJECTED`.

## Validation boundary

The Python implementation is subject to CI and host validation. Existing
Automation artifacts remain evidence/input until explicitly imported, hashed,
classified, and validated. Host validation does not imply physical Android
validation.

Remote queues may request allowlisted capabilities. They must not become
unrestricted remote shells. See [SECURITY.md](SECURITY.md).

© 2026 Robert Frost
