# Automation OS / Frost Forge Project Consolidation

Version: 2.3
Status: CANONICAL / HOST_V1_VERIFIED_COMPLETE / PHYSICAL_GATE_EXTERNAL
Canonical repository: `12ephods-source/centinal26`
Canonical production branch: `main`
Frozen host baseline: `9446a7afb214e413d1fbb87f09781272fac350c6`

## Source-of-Truth Hierarchy

1. Git history, exact-head CI, durable workflow ledgers, immutable artifacts, and explicit external-gate issues are primary evidence.
2. This file is the canonical human-readable continuation authority.
3. `automation/PROJECT_STATE.json` is the canonical machine-readable continuation state.
4. `PROJECT_STATE_AUTOMATION_OS.md` is the concise summary and defers to the sources above if they diverge.

## Terminal Objective

Operate a reusable evidence-centered automation platform that turns project intent into bounded execution, independent verification, persistent evidence, reusable capabilities, integrated features, and release candidates while preserving a narrow recovery trust root and explicit validation boundaries.

## Canonical Invariant Pipeline

`Intent -> Authorization -> Event/Queue -> Capability Selection -> Bounded Execution -> Verification -> Evidence/Audit -> State Update -> Controlled Evolution`

Execution transaction:

`INTENT -> AUTHORIZATION -> PRECONDITIONS -> BASELINE -> BOUNDED EXECUTION -> POSTCONDITIONS -> INDEPENDENT VERIFICATION -> EVIDENCE -> STATE UPDATE -> ROLLBACK/PROMOTION`

## Control Plane

Frost Master Project Protocol v3 is the active canonical control plane. Protocol v2 remains historical provenance.

The production role model is Planner / Builder / Judge / SRE / Sentinel / Release. Judge and Sentinel are non-mutating by default. Consequential mutations require independent Judge verification. Protected recovery-root operations remain denied.

## Verified Host Architecture

The verified host baseline contains:

- Project Productizer with Protocol v3 provenance binding and hashed outputs.
- Agent qualification fleet and bounded operational execution plane.
- Durable execution evidence and issue ledger.
- Named reusable execution profiles rather than arbitrary reusable command input.
- Expanded bounded authority policy and recovery-root deny policy.
- Runtime executor interface, executor registry, repository/API/Android-worker contracts, and executor-integration CI.
- Productizer -> generated artifacts -> independent Judge end-to-end host validation.
- Manifest-driven Android/Termux universal installer with immutable module identities and fail-closed module management.
- Android/Termux evidence capture with SHA-256 manifest generation and host/tamper rejection.
- Controller-side device evidence verification.
- Worker heartbeat record software with device identity, boot ID, enrollment digest, freshness, Android/Termux signal, and record-hash binding.
- Controller-side worker heartbeat verifier.
- Pinned Termux keyring recovery path.
- CI, Automation Validation, validate, automation-gates, federation-gates, Executor Integration Validation where applicable, and Mature Product Qualification.

## Canonical Lineage

- PR #174 — Project Productizer.
- PR #177 — Protocol v2 clean artifacts.
- PR #181 — Protocol v3 execution-first control plane.
- PR #187 — repository Ruff convergence.
- PR #190 — operational Agent Execution Plane.
- PR #192 — event-driven failure-complete execution.
- PR #193 — runtime executor contract unification.
- PR #194 — Productizer-to-Judge end-to-end closure.
- PR #196 — canonical continuation consolidation.
- PR #197 — durable bounded execution ledger.
- PR #200 — bounded authority-policy reconciliation.
- PR #203 — physical worker heartbeat activation-gate host software.
- PR #204 — qualified universal Termux installer host software.
- PR #206 — physical-gate continuation-state finalization.

Superseded implementation paths include PR #175, #176, #179, #180, #182, #183, #184, #185, #186, #188, #189, #191, and accidental redundant PR #207. They remain provenance only.

## Production Evidence

Agent runtime verification after authority deployment:

- merge commit `883673d8ae03be09d0db0cc646e9a0c7b4ab692a`;
- workflow run `32488911036`;
- durable issue #199;
- Judge / `agent-tests` / PASS;
- 9 execution-plane tests PASS;
- task digest `984878fc3193a34e180ae46bdde81d3458fbe139c7043a2c257193a404d05743`;
- evidence digest `20681ea2c49fbe28f04b70f4c3366ed73c09f40945f0f2f253c5d39f3aea4f76`;
- artifact #9448948270 with digest `sha256:7d2368ec67390701ca1ef589bfe559c5dc69d1a4025714e99c3aaf92a365c9d2`.

Host baseline qualification after installer/heartbeat integration and state finalization:

- production baseline `9446a7afb214e413d1fbb87f09781272fac350c6`;
- PR #206 exact head passed CI, Automation Validation, validate, automation-gates, federation-gates, and Mature Product Qualification.

## External Gate Trackers

- Issue #208 — canonical Android/Termux physical qualification gate.
- Issue #209 — external connector qualification matrix.
- Issue #199 — durable Agent Execution Plane status ledger.

## Physical Android Gate

`AUTOMATION_PLATFORM_V1_PHYSICAL_DEVICE = BLOCKED_EXTERNAL_PHYSICAL_EVIDENCE`

This is not an unfinished host-software state. The software path exists. Completion requires facts that must originate from a real authorized Android/Termux device:

1. Run the current one-paste enrollment/evidence path on the device.
2. Preserve the generated evidence bundle before interpretation.
3. Controller-verify manifest hashes, Android-origin signals, boot ID, package inventory, and enrollment invariants.
4. Require `VERIFIED_ELIGIBLE`; captured evidence alone is insufficient.
5. Emit a heartbeat bound to the verified enrollment digest and boot session.
6. Controller-verify heartbeat identity, hash, freshness, Android/Termux signal, enrollment digest, and boot ID.
7. Execute one harmless bounded Android-worker qualification task.
8. Preserve execution evidence and independent Judge result.

Host/CI execution cannot legitimately substitute for these observations.

## Connector Qualification

`AUTOMATION_PLATFORM_V1_EXTERNAL_CONNECTORS = PARTIAL_WITH_GITHUB_VERIFIED`

The live GitHub connector for the currently authorized `12ephods-source/centinal26` repository scope is verified for read/write operation. Observed live actions include repository reads, PR creation/update/merge, workflow inspection, and issue creation/update. Issue #209 tracks this evidence.

The repository `api_connector_executor` remains `VERIFIED_SOFTWARE`; authorization is target-specific. Every other external connector must cross the ladder:

`ADAPTER_PRESENT -> AUTHENTICATED -> AUTHORIZED -> LIVE_EXECUTED -> INDEPENDENTLY_VERIFIED -> PRODUCTION_QUALIFIED`

One verified connector does not imply a global connector PASS.

## Validation Boundaries

Mandatory distinctions:

- queued != executed != verified;
- installed != authorized;
- executor available != executor verified;
- host/CI PASS != physical-device PASS;
- captured device evidence != controller-verified enrollment != active worker;
- verified heartbeat software != real-device heartbeat;
- one connector verified != all connectors verified;
- integration PASS != production external-connector PASS;
- evidence existence != accessibility != acquisition != integrity != verification != interpretation;
- absence of observed evidence != evidence of absence.

## Release State

`AUTOMATION_PLATFORM_V1_HOST = VERIFIED_COMPLETE`

`AUTOMATION_PLATFORM_V1_PHYSICAL_DEVICE = BLOCKED_EXTERNAL_PHYSICAL_EVIDENCE`

`AUTOMATION_PLATFORM_V1_EXTERNAL_CONNECTORS = PARTIAL_WITH_GITHUB_VERIFIED`

Do not collapse these states into a single global PASS.

## Critical Path

1. Acquire real Android/Termux device-origin evidence under issue #208.
2. Controller-verify the physical bundle.
3. Observe and verify worker heartbeat bound to the verified enrollment.
4. Execute one bounded Android-worker task and preserve independent evidence.
5. Qualify remaining external connectors individually under issue #209.
6. Re-run exact-head qualification and promote only the gates actually satisfied.

## Stop / Continuation Rule

Continue automatically through available bounded implementation, tests, diagnosis, repair, qualification, integration, and promotion. Stop only at verified completion or a genuine physical/external dependency, authorization/platform boundary, falsified terminal gate, superseded objective, or negative expected value.

This record is a continuation index, not a substitute for Git history or source evidence.
