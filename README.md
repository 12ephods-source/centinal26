# Automation OS — Frost Forge

Canonical implementation repository for the Frost Automation project.

**Frost Forge** is the canonical human-facing name of the active Automation OS line. `Wazoo26` is retained as a former human-facing compatibility name, while the repository slug, Python distribution/import path, legacy CLI, state directory, historical release identifiers, hashes, and provenance records retain `centinal26` where changing them would break compatibility or falsify history.

Frost Forge is a local-first, evidence-centered automation runtime. It is designed so that increasing autonomy does not weaken authorization, execution bounds, verification, provenance, or release control.

## Status snapshot

The current platform state and historical package/recovery identifiers are intentionally separate:

| Axis | Current value | Meaning |
|---|---|---|
| Automation Platform v1 host | `VERIFIED_COMPLETE` | Canonical host/runtime implementation is integrated and qualified |
| Runtime governance | `VERIFIED_COMPLETE_HOST` | Objective, authorization, capability-token, bounded-execution, verification, and evidence gates are enforced on host |
| Physical Android/Termux | `BLOCKED_EXTERNAL_PHYSICAL_EVIDENCE` | Real device-origin commissioning plus bounded worker execution is still required |
| Reboot persistence | `BLOCKED_ON_DEVICE_VALIDATED_AND_PHYSICAL_REBOOT` | Requires Phase A device validation, physical reboot, verified return, and post-reboot work |
| External connectors | `PARTIAL_WITH_MULTIPLE_VERIFIED_SCOPES` | Several scoped connectors are live-verified; qualification remains operation-specific |
| Python compatibility package | `centinal26 0.1.0` | Compatibility distribution implementing Frost Forge in `src/centinal26/` |
| Historical recovery/bootstrap state | `0.0.4-rc4-parent-recovery` | Preserved recovery/control provenance, not the current host-platform status |
| Historical recoverable release target | `1.0.0-rc4-converged` / `REVIEW` | Preserved historical release-control lineage; not equivalent to current Automation Platform v1 host state |

Canonical continuation state is maintained in `AUTOMATION_OS_RUNTIME_CONSOLIDATION.md`, `automation/PROJECT_STATE.json`, and `PROJECT_STATE_AUTOMATION_OS.md`. Current synchronized generation is v2.7. Git history, exact-head CI, immutable artifacts, durable ledgers, issue #208, issue #209, and live control-plane observations remain primary evidence.

The qualified Android physical-commissioning source is `9c0925ee7e3dc23f6e81718f9c1a2ca7926ec483`. Host validation does **not** imply physical Android/Termux validation.

## Naming and compatibility

Canonical product name: `Frost Forge` / `Automation OS`.

Compatibility identifiers retained deliberately:

- former human-facing name: `Wazoo26`
- GitHub repository: `12ephods-source/centinal26`
- Python distribution/import package: `centinal26`
- compatibility CLI aliases: `wazoo26`, `centinal26`
- default state directory: `~/.local/state/centinal26`
- compatibility state variables: `WAZOO26_HOME`, `CENTINAL26_HOME`

`WAZOO26_HOME` takes precedence over `CENTINAL26_HOME`; if neither is set, the existing state directory remains unchanged. These compatibility identifiers do not redefine the current Frost Forge project identity.

Historical artifacts are not rewritten merely to replace old names. See `docs/WAZOO26_RENAME.md` for the earlier rename lineage.

## Core invariant

Every consequential operation follows:

`Intent → Authorization → Event/Queue → Capability Selection → Bounded Execution → Verification → Evidence/Audit → State Update → Controlled Evolution`

Consequential verification must be independent where the applicable gate requires it. No module may bypass authorization, bounded execution, verification, or audit to gain convenience or autonomy.

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

The `wazoo26` and `centinal26` CLI names remain compatibility entry points for the Frost Forge runtime.

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
- Planner / Builder / Judge / SRE / Sentinel / Release role semantics
- durable agent-execution evidence and named bounded execution profiles
- runtime executor registry and integration validation
- deterministic governance and objective-integrity enforcement
- Project Productizer → Judge end-to-end host validation
- manifest-driven Termux installer and source-bound physical commissioning
- normalized Android/Termux device-profile capture plus raw device evidence
- controller-side enrollment, heartbeat, and commissioning verification
- automated vertical-slice execution with lease recovery and evidence output
- pytest invariant tests and Ruff linting
- CI across Python 3.11, 3.12, and 3.13

Primary compatibility CLI commands:

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

Frost Forge treats automation as an authorized state transition, not unrestricted command execution.

The enforced baseline includes:

1. A submitted job names a registered capability.
2. A grant must match that capability and remain unexpired.
3. Input is structured JSON; the core does not accept shell source.
4. State transitions persist in durable state.
5. Audit events form a SHA-256 hash chain.
6. Failed and rejected jobs remain evidence rather than being erased.
7. Consequential execution requires canonical objective/authorization/capability context and remains independently verifiable.

A SHA-256 pin proves byte identity, not benign behavior. External executable artifacts therefore require separate identity and behavior gates before execution.

Autonomous agents are bounded executors/proposers, not recovery-root authority. Controlled evolution remains constrained by independent policy, validation, evidence, and promotion gates.

See `SECURITY.md` for the full trust-boundary model.

## Current physical-release boundary

GitHub issue #208 is the canonical Android/Termux qualification tracker. The current qualified commissioning source is:

`9c0925ee7e3dc23f6e81718f9c1a2ca7926ec483`

Phase A requires:

`source-bound Android commissioning ZIP → controller verification → verified enrollment/heartbeat → same Android worker observed → one harmless bounded device task → independent Judge evidence → DEVICE_VALIDATED eligibility`

Phase B requires:

`preserve pre-reboot identity → physical local reboot → changed boot_id → worker/controller return → fresh verified heartbeat → valid lease/event chain → one harmless post-reboot task → independent Judge evidence → PERSISTENT_VALIDATED eligibility`

Historical issue #64, RC9, RC3/RC4 finalizers, and their release artifacts remain provenance/compatibility material. They do not replace issue #208 as the current physical acceptance path. A historical `REVIEW` record remains a historical record and does not override current v2.7 host truth.

No host result may be promoted to physical-device validation. Missing exact bytes remain missing exact bytes; reconstruction does not silently become provenance-equivalent to an original artifact.

## Connector state

Issue #209 is the connector qualification matrix. Current demonstrated scopes include:

- GitHub: live read/write for the authorized Centinal26 repository scope
- Base44: live read/write for the authorized Automation entity scope
- Gmail: scoped reversible live write
- Google Calendar: scoped reversible live write
- Google Drive: scoped reversible live write
- Google Contacts: authenticated read; no reversible write surface currently exposed
- Notion: authenticated read verified
- Linear: authenticated read verified

Connector qualification is operation- and scope-specific. One verified connector or operation never grants global connector authority.

The first-party Vercel controller software is host-qualified, but live deployment is a separate authorization boundary. The current deployment ledger is issue #228.

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

The repository distinguishes at least:

```text
source/provenance known
        ↓
static validation
        ↓
host validation
        ↓
physical Android/Termux commissioning
        ↓
bounded real-device work
        ↓
DEVICE_VALIDATED
        ↓
physical reboot + verified return + post-reboot work
        ↓
PERSISTENT_VALIDATED
        ↓
release qualification / explicit evidence-gated promotion
```

A higher stage may not be inferred from a lower one.

## Layout

- `src/centinal26/` — Frost Forge runnable orchestration core and compatibility CLI package
- `automation/` — canonical Automation OS state, runtime executors, deployment, verification, and integration machinery
- `workers/` — bounded workers and job consumers
- `deploy/termux/`, `scripts/` — Android/Termux deployment and compatibility tooling
- `schemas/` — job, evidence, audit, artifact, and release schemas
- `tests/` — invariant, schema, runtime, provenance, and release-gate validation
- `docs/` — architecture, timeline, operating model, provenance
- `.github/workflows/` — automated validation and bounded deployment coordination
- `releases/` — release manifests, historical evidence, and release-control state
- `candidates/` — useful integrations not promoted into canonical release lineage
- `provenance/` — artifact identities, classifications, hashes, and validation boundaries

## What this repository does not claim

Frost Forge does not claim that:

- GitHub is an Android execution host.
- A host test proves a physical-device result.
- A hash proves an artifact is safe.
- An AI agent's approval is sufficient authorization.
- A recovered or reconstructed file is byte-identical to a missing original without matching evidence.
- Remote automation may bypass the registered capability interface and become a general-purpose shell.
- `REVIEW` is equivalent to GA.
- a user-supplied device profile is equivalent to controller-verified physical evidence.
- a commissioning PASS is equivalent to bounded worker-task PASS or reboot persistence.

Those distinctions are part of the architecture, not documentation caveats.

© 2026 Robert Frost
