# Automation OS — Centinal26

Canonical implementation repository for Robert Frost's Automation project.

## Core invariant

Every consequential operation follows:

`Intent → Authorization → Event/Queue → Capability Selection → Bounded Execution → Verification → Evidence/Audit → State Update → Controlled Evolution`

No module may bypass authorization, bounded execution, verification, or audit to gain convenience or autonomy.

## Working baseline

The repository contains a runnable Python 3.11+ core:

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

## Automated vertical slice

The additive automated runtime closes the canonical path through independently declared verification, immutable per-attempt evidence, evidence-gated state updates, idempotent durable submission, bounded retries, expiring worker leases, and crash recovery.

```bash
centinal26 auto-demo
centinal26 auto-selftest
centinal26 auto-status
centinal26 auto-daemon --poll 2
```

`bash scripts/host-automation-gate.sh` executes ten verified passes plus a lease-recovery pass. GitHub Actions runs the same gate on pushes, pull requests, manual dispatch, and a daily schedule and preserves the host evidence as an artifact. The gate may report `evolution.ready=true`; that is runtime readiness only and never automatic GA promotion or physical-device validation.

For opt-in Android boot persistence, `bash scripts/enable-termux-boot.sh` installs the bounded daemon as a Termux:Boot hook. See `docs/AUTOMATED_VERTICAL_SLICE.md`.

## Repository role

GitHub is the durable engineering source of truth: code, deployment assets,
tests, schemas, CI, release manifests, provenance, and history. Device-side
execution remains in Termux/Hermes/local workers; GitHub does not itself
execute Android commands.

## Current release-control state

- Highest recoverable canonical release target: `1.0.0-rc4-converged`, schema 10.
- Current release decision: `REVIEW`, not GA.
- RC3 GA-campaign evidence is retained under `releases/1.0.0-rc3-ga-campaign/` as superseded release history.
- The exact RC4 all-in-one orchestrator and embedded v6 bundle are registered by known identity/hash when bytes are not mounted; they are not reconstructed as originals.
- FROST Automation OS v1.0 is retained under `candidates/` as a host-validated compatible integration candidate; its physical Android/Termux gate remains open.
- No host result may be promoted to physical-device validation.

See `provenance/ARTIFACT_REGISTRY.json` and `releases/BOOTSTRAP_STATE.json` for machine-readable status.

## Layout

- `src/centinal26/` — runnable orchestration core and CLI
- `workers/` — bounded workers and job consumers
- `deploy/termux/`, `scripts/` — Android/Termux deployment
- `schemas/` — intent, job, evidence, audit, artifact, and release schemas
- `tests/` — invariant, schema, runtime, provenance, and release-gate validation
- `docs/` — architecture, timeline, operating model, provenance
- `.github/workflows/` — automated validation
- `releases/` — release manifests, historical evidence, and release-control state
- `candidates/` — useful integrations not promoted into canonical release lineage
- `provenance/` — artifact identities, classifications, hashes, and validation boundaries

## Subsystem status taxonomy

Every imported or evolved subsystem must be classified as one of
`CANONICAL`, `COMPATIBLE_MODULE`, `EXPERIMENTAL`, `SUPERSEDED`, or
`REJECTED`.

## Validation boundary

Host validation does not imply physical Android validation. Existing
Automation artifacts become canonical only through explicit provenance,
classification, validation, and release-control decisions.

Remote queues may request allowlisted capabilities. They must not become
unrestricted remote shells. See [SECURITY.md](SECURITY.md).

© 2026 Robert Frost
