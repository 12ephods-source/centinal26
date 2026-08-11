# Automation OS

Canonical implementation repository for Robert Frost's Automation project.

## Core invariant

Every consequential operation follows:

`Intent → Authorization → Event/Queue → Capability Selection → Bounded Execution → Verification → Evidence/Audit → State Update → Controlled Evolution`

No module may bypass authorization, bounded execution, verification, or audit to gain convenience or autonomy.

## Repository role

GitHub is the durable engineering source of truth: code, deployment assets, tests, schemas, CI, release manifests, and history. Device-side execution remains in Termux/Hermes/local workers; GitHub does not itself execute Android commands.

## Layout

- `src/` — orchestration/runtime code and capability interfaces
- `workers/` — bounded workers and job consumers
- `deploy/termux/` — Android/Termux bootstrap and service scripts
- `schemas/` — job, evidence, audit, capability, and release schemas
- `tests/` — invariant, schema, and runtime validation
- `docs/` — architecture, threat model, operating model, provenance
- `.github/workflows/` — automated validation
- `releases/` — release manifests and validation state

## Subsystem status taxonomy

Every imported or evolved subsystem must be classified as one of:

- `CANONICAL`
- `COMPATIBLE_MODULE`
- `EXPERIMENTAL`
- `SUPERSEDED`
- `REJECTED`

## Current maturity

Repository bootstrap is in progress. Existing Automation artifacts remain evidence/input until explicitly imported, hashed, classified, and validated. Host validation does not imply physical Android validation.

## Safety boundary

Remote queues may request allowlisted capabilities. They must not become unrestricted remote shells. Consequential execution should be explicit, bounded, auditable, and reversible where practical.
