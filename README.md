# Automation OS — Wazoo26

Canonical implementation repository for Robert Frost's Automation project.

**Wazoo26** is the canonical human-facing name of the active Automation OS line formerly called Centinal26. The repository slug, Python distribution/import path, legacy CLI, state directory, historical release identifiers, hashes, and provenance records retain `centinal26` where changing them would break compatibility or falsify history.

Wazoo26 is a local-first, evidence-centered automation runtime. It is designed so that increasing autonomy does not weaken authorization, execution bounds, verification, provenance, or release control.

## Status snapshot

Wazoo26 currently has three distinct version/state axes. They are intentionally separate:

| Axis | Current value | Meaning |
|---|---|---|
| Python runtime package | `centinal26 0.1.0` | Compatibility distribution implementing Wazoo26 in `src/centinal26/` |
| Recovery/bootstrap control state | `0.0.4-rc4-parent-recovery` | Static-validated recovery/control metadata in `releases/BOOTSTRAP_STATE.json` |
| Highest recoverable canonical release target | `1.0.0-rc4-converged` | Release-control target; current decision is `REVIEW`, not GA |

Host validation does **not** imply physical Android/Termux validation. The current release-control state does not claim Android-device validation, endurance validation, device-sync validation, recovery-drill validation, native-candidate certification, or explicit human promotion.

## Naming and compatibility

Canonical product name: `Wazoo26`.

Compatibility identifiers retained deliberately:

- GitHub repository: `12ephods-source/centinal26`
- Python distribution/import package: `centinal26`
- legacy CLI: `centinal26`
- default state directory: `~/.local/state/centinal26`
- legacy state variable: `CENTINAL26_HOME`

New interfaces:

- canonical CLI alias: `wazoo26`
- canonical state variable: `WAZOO26_HOME`

`WAZOO26_HOME` takes precedence over `CENTINAL26_HOME`; if neither is set, the existing state directory remains unchanged so the rename does not fork runtime state.

Historical artifacts are not rewritten merely to replace the old name. See `docs/WAZOO26_RENAME.md`.

## Core invariant

Every consequential operation follows:

`Intent → Authorization → Event/Queue → Capability Selection → Bounded Execution → Verification → Evidence/Audit → State Update → Controlled Evolution`

No module may bypass authorization, bounded execution, verification, or audit to gain convenience or autonomy.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"

wazoo26 init
wazoo26 demo
wazoo26 status
pytest
```

The legacy `centinal26` CLI remains available as a compatibility alias.

State defaults to `~/.local/state/centinal26`. Set `WAZOO26_HOME` to override it; `CENTINAL26_HOME` remains supported for compatibility.

Termux bootstrap:

```bash
bash scripts/install-termux.sh
```

## Runnable baseline

The repository contains a runnable Python 3.11+ core with:

- explicit, expiring capability grants
- registered capability allowlists; no arbitrary shell execution
- structured job input rather than shell source
- durable SQLite job queues and state transitions
- append-only SHA-256 hash-linked audit records
- failed and rejected jobs preserved as evidence
- verification before successful state advancement
- CLI initialization, demonstration, worker-step, status, qualification, and evidence commands
- automated vertical-slice execution with lease recovery and evidence output
- pytest invariant tests and Ruff linting
- CI across Python 3.11, 3.12, and 3.13
- Termux installation/bootstrap assets

Primary CLI commands:

```text
wazoo26 init
wazoo26 demo
wazoo26 run-once
wazoo26 status
wazoo26 qualify --output <path>
wazoo26 verify-evidence <bundle>
wazoo26 assess-evidence <bundle> [--output <path>]
```

Automated-runtime commands:

```text
wazoo26 auto-demo
wazoo26 auto-run-once
wazoo26 auto-daemon [--poll <seconds>]
wazoo26 auto-selftest
wazoo26 auto-status
```

`auto-selftest` exercises the automated queue's lease-recovery path before executing the recovered job.

## Repository role and execution boundary

GitHub is the durable engineering source of truth for:

- code
- deployment assets
- tests and schemas
- CI
- release manifests
- provenance
- historical evidence and superseded states

Device-side execution remains in Termux/Hermes/local workers. GitHub does not itself execute Android commands.

Remote queues may request registered, allowlisted capabilities. They must not become unrestricted remote shells.

The intended boundary is:

```text
remote/local intent
    ↓
authorization / capability grant
    ↓
durable queue
    ↓
registered semantic capability
    ↓
bounded worker execution
    ↓
independent verification where available
    ↓
evidence + hash-linked audit
    ↓
state transition / release-control decision
```

## Security model

Wazoo26 treats automation as an authorized state transition, not unrestricted command execution.

The enforced baseline includes:

1. A submitted job names a registered capability.
2. A grant must match that capability and remain unexpired.
3. Input is structured JSON; the core does not accept shell source.
4. State transitions persist in SQLite.
5. Audit events form a SHA-256 hash chain.
6. Failed and rejected jobs remain evidence rather than being erased.

A SHA-256 pin proves byte identity, not benign behavior. External executable artifacts therefore require separate identity and behavior gates before execution.

Autonomous agents are proposers, not authority. Controlled evolution must remain bounded by independent policy, validation, evidence, and promotion gates.

See [SECURITY.md](SECURITY.md) for the full trust-boundary model.

## Current release-control state

- Highest recoverable canonical release target: `1.0.0-rc4-converged`, schema 10.
- Current release decision: `REVIEW`, not GA.
- RC3 GA-campaign evidence is retained under `releases/1.0.0-rc3-ga-campaign/` as superseded release history.
- The exact RC4 all-in-one orchestrator and embedded v6 bundle are registered by known identity/hash when bytes are not mounted; they are not reconstructed as originals.
- FROST Automation OS v1.0 is retained under `candidates/` as a host-validated compatible integration candidate; its physical Android/Termux gate remains open.
- No host result may be promoted to physical-device validation.
- Missing exact bytes remain missing exact bytes; reconstruction does not silently become provenance-equivalent to an original artifact.

Machine-readable release/provenance state:

- `provenance/ARTIFACT_REGISTRY.json`
- `releases/BOOTSTRAP_STATE.json`

## Canonicalization and subsystem status

Every imported or evolved subsystem must be classified as exactly one of:

- `CANONICAL`
- `COMPATIBLE_MODULE`
- `EXPERIMENTAL`
- `SUPERSEDED`
- `REJECTED`

Existing Automation artifacts become canonical only through explicit provenance, classification, validation, and release-control decisions.

A useful implementation is not automatically a canonical implementation. A host-validated implementation is not automatically device-validated. A known hash is not automatically a safety verdict.

## Validation boundary

Validation claims must identify their execution environment and evidence level.

The repository currently distinguishes at least:

```text
source/provenance known
        ↓
static validation
        ↓
host validation
        ↓
physical Android/Termux validation
        ↓
endurance / sync / recovery evidence
        ↓
release certification
        ↓
explicit promotion
```

A higher stage may not be inferred from a lower one.

## Layout

- `src/centinal26/` — Wazoo26 runnable orchestration core and CLI compatibility package
- `workers/` — bounded workers and job consumers
- `deploy/termux/`, `scripts/` — Android/Termux deployment
- `schemas/` — job, evidence, audit, artifact, and release schemas
- `tests/` — invariant, schema, runtime, provenance, and release-gate validation
- `docs/` — architecture, timeline, operating model, provenance
- `.github/workflows/` — automated validation
- `releases/` — release manifests, historical evidence, and release-control state
- `candidates/` — useful integrations not promoted into canonical release lineage
- `provenance/` — artifact identities, classifications, hashes, and validation boundaries

## What this repository does not claim

Wazoo26 does not claim that:

- GitHub is an Android execution host.
- A host test proves a physical-device result.
- A hash proves an artifact is safe.
- An AI agent's approval is sufficient authorization.
- A recovered or reconstructed file is byte-identical to a missing original without matching evidence.
- Remote automation may bypass the registered capability interface and become a general-purpose shell.
- `REVIEW` is equivalent to GA.

Those distinctions are part of the architecture, not documentation caveats.

© 2026 Robert Frost
