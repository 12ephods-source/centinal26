# Automation OS / Frost Forge Project Consolidation

Version: 2.1
Status: CANONICAL / HOST_V1_VERIFIED_COMPLETE
Canonical repository: `12ephods-source/centinal26`
Canonical production branch: `main`
Observed production head for this refresh: `9c5e89b17eeb95b0e456f3f3428df80e7b4a9283`

## Source-of-Truth Hierarchy

1. Git history, exact-head CI evidence, durable workflow ledgers, and immutable artifacts remain primary evidence.
2. This file is the canonical human-readable continuation authority for the Automation project.
3. `automation/PROJECT_STATE.json` is the canonical machine-readable continuation state.
4. `PROJECT_STATE_AUTOMATION_OS.md` is the concise production-state summary and must defer to the two canonical continuation records above if they diverge.

## Terminal Objective

Build and operate a reusable, evidence-centered automation platform that turns project intent into bounded execution, independent verification, persistent evidence, reusable capabilities, integrated features, and release candidates while preserving a narrow recovery trust root and explicit validation boundaries.

## Canonical Invariant Pipeline

`Intent -> Authorization -> Event/Queue -> Capability Selection -> Bounded Execution -> Verification -> Evidence/Audit -> State Update -> Controlled Evolution`

Execution transaction:

`INTENT -> AUTHORIZATION -> PRECONDITIONS -> BASELINE -> BOUNDED EXECUTION -> POSTCONDITIONS -> INDEPENDENT VERIFICATION -> EVIDENCE -> STATE UPDATE -> ROLLBACK/PROMOTION`

## Control Plane

Active canonical protocol: Frost Master Project Protocol v3.

Protocol v3 establishes terminal-objective dominance, act-before-explain behavior, critical-path prioritization, evidence-conditioned BUILD -> TEST -> DIAGNOSE -> REPAIR -> RETEST -> INDEPENDENT_VERIFY -> INTEGRATE -> DEPLOY -> VERIFY_DEPLOYMENT, role separation, failure memory, anti-loop behavior, machine-readable state, and explicit stop conditions.

Protocol v2 remains historical provenance and is superseded for active control by v3.

## Production Architecture

```text
Goal / Project Intent
        |
        v
Project State / Productizer
        |
        v
Task Router / Scheduler / Queue
        |
        v
Agent + Capability Selection
        |
        v
Authority Policy / Recovery Root
        |
        v
Executor Registry
  |       |       |       |
 local   repo     API   Android worker
        |
        v
Bounded Agent Execution Plane
Planner / Builder / Judge / SRE / Sentinel / Release
        |
        v
Evidence Generation + Hashing + Durable Status Ledger
        |
        v
Independent Validation / Mature Product Gates
        |
        v
Audit / Product State / Release Decision
```

## Verified Production Capabilities

Deployed or represented by merged production commits:

- Project Productizer generating prompt bootstrap, project brief, feature registry, product roadmap, and hashed manifest.
- Protocol v2 historical artifacts and propagation verifier.
- Protocol v3 execution-first control kernel.
- Agent qualification fleet and CI qualification surfaces.
- Operational Planner/Builder/Judge/SRE/Sentinel/Release execution semantics.
- Bounded subprocess execution with timeout limits and structured terminal evidence.
- Expanded recovery-root deny boundary covering ownership, authentication/recovery factors, independent audit/backup destruction, unrestricted credential issuance, billing authority, and root-policy self-modification.
- Judge and Sentinel non-mutating defaults; consequential mutation requires independent Judge verification.
- Task/evidence SHA-256 digests and failure-complete evidence records.
- Reusable GitHub Actions workflow restricted to named execution profiles rather than arbitrary reusable command input.
- Durable GitHub issue ledger plus machine-readable task/evidence/status artifacts.
- Runtime executor interface and executor registry.
- Local Python, repository, API connector, Android worker, and canonical agent-plane executor contracts.
- Executor capability metadata and unified request contract.
- Executor integration harness connected to CI.
- Project Productizer -> canonical Protocol v3 provenance binding -> independent Judge verification.
- Android/Termux device-origin evidence collector and one-paste enrollment runner.
- Controller-side physical evidence integrity/origin verifier that fails closed on host or tampered evidence.
- CI, validate, automation-gates, federation-gates, Executor Integration Validation, and Mature Product Qualification.

## Canonical Software Lineage

- PR #174: Project Productizer — MERGED / CANONICAL.
- PR #177: Protocol v2 clean artifacts — MERGED / HISTORICAL CANONICAL.
- PR #181: Protocol v3 — MERGED / ACTIVE CANONICAL CONTROL PLANE.
- PR #187: repository Ruff convergence — MERGED / MAINTENANCE HISTORY.
- PR #190: operational Agent Execution Plane — MERGED / CANONICAL.
- PR #192: event-driven, failure-complete execution — MERGED / CANONICAL.
- PR #193: runtime executor contract unification — MERGED / CANONICAL.
- PR #194: Productizer-to-Judge end-to-end closure — MERGED / CANONICAL.
- PR #196: canonical continuation consolidation — MERGED / CANONICAL STATE.
- PR #197: durable bounded Agent Execution Plane ledger — MERGED / CANONICAL.
- PR #200: bounded agent authority policy reconciliation — MERGED / CANONICAL.

PR #197 production verification:
- merge commit `fc1cb13696099e5cf32f43f55f7c1fc8868a31d0`;
- production push run `32488588742`;
- Judge / `agent-tests` / PASS;
- durable issue #199 created;
- machine artifact retained with SHA-256 digest.

PR #200 production verification:
- merge commit `883673d8ae03be09d0db0cc646e9a0c7b4ab692a`;
- production push run `32488911036`;
- Judge / `agent-tests` / PASS;
- 9 execution-plane regressions PASS;
- task digest `984878fc3193a34e180ae46bdde81d3458fbe139c7043a2c257193a404d05743`;
- evidence digest `20681ea2c49fbe28f04b70f4c3366ed73c09f40945f0f2f253c5d39f3aea4f76`;
- workflow artifact #9448948270 retained with digest `sha256:7d2368ec67390701ca1ef589bfe559c5dc69d1a4025714e99c3aaf92a365c9d2`.

## Supersession Record

Do not use PR #176, #179, #180, #182, #183, #184, #185, #186, #188, #189, or #191 for new implementation. They remain historical design/failure/reconstruction provenance only.

The useful authority semantics from PR #179 were transplanted into the canonical runtime by PR #200; #179 is closed as superseded.

## Validation Boundaries

Mandatory distinctions:

- queued != executed != verified;
- installed != authorized;
- executor available != executor verified;
- host/CI PASS != physical-device PASS;
- captured Android evidence != controller-verified enrollment != active worker;
- integration PASS != production external-connector PASS;
- numerical/software consistency != empirical/scientific confirmation;
- evidence existence != accessibility != acquisition != integrity != verification != interpretation;
- absence of observed evidence != evidence of absence.

## Trust / Authority Model

`config/agent_authority.json` and the canonical `src/centinal26/agent_execution_plane.py` now implement the active bounded authority policy.

Qualified roles: Planner, Builder, Judge, SRE, Sentinel, Release.

Judge and Sentinel are non-mutating by default. Planner, Builder, SRE, and Release may perform policy-authorized bounded mutations. Consequential mutations require independent Judge verification. Protected recovery-root operations remain denied. Provider authentication, account/org ownership controls, third-party authorization, credential recovery controls, and other platform-enforced boundaries remain external mandatory controls.

## Completed Internal Workstreams

### Durable Agent Execution Ledger — VERIFIED_COMPLETE

PR #197 is deployed and production-verified. Reusable callers select named profiles (`agent-tests`, `full-tests`, `lint`, `fleet-qualify`) instead of arbitrary command strings. The workflow retains machine-readable evidence and updates durable issue #199.

### Agent Authority Policy — VERIFIED_COMPLETE

PR #200 is deployed and production-verified. Stale PR #179 is superseded and closed.

## Active Workstreams

### A. Android/Termux Physical Validation — PENDING_PHYSICAL_EVIDENCE

Software now exists on `main` to:
- perform one-paste Termux setup;
- capture Android/Termux environment and package inventory evidence;
- generate SHA-256 manifests;
- reject non-Android host execution as physical PASS;
- controller-verify bundle integrity, Android-origin signals, boot ID, and package inventory.

The gate still requires execution on a real authorized Android device. Physical PASS cannot be manufactured by CI.

### B. Real Android Worker Activation — PENDING_PHYSICAL

After a bundle is controller-verified as `VERIFIED_ELIGIBLE`, worker activation remains heartbeat-gated. A bounded task must then execute through the Android worker executor and produce preserved post-execution evidence before the worker path is promoted.

### C. Production Connector Authorization — PARTIAL

Repository/API executor contracts exist. Each real external connector still requires supported authentication/authorization and connector-specific live execution evidence.

## Release State

`AUTOMATION_PLATFORM_V1_HOST = VERIFIED_COMPLETE`

Verified host/CI scope includes deterministic project productization, Protocol v3 provenance, operational bounded agent execution, independent Judge verification, durable status evidence, bounded authority, runtime executor integration, and mature-product host qualification.

`AUTOMATION_PLATFORM_V1_PHYSICAL_DEVICE = PENDING_PHYSICAL_EVIDENCE`

`AUTOMATION_PLATFORM_V1_EXTERNAL_CONNECTORS = PARTIAL`

Do not collapse these three states into a single global PASS.

## Critical Path

1. Preserve this refreshed canonical state.
2. Execute `automation/deployment/enrollment_package/termux_enroll_onepaste.sh` on one real authorized Android/Termux device.
3. Return and controller-verify the generated evidence bundle.
4. Observe a valid worker heartbeat for the verified device identity/boot session.
5. Execute one bounded Android-worker task and preserve independent post-execution evidence.
6. Promote production connector adapters individually after connector-specific authorization and verification.

## Stop / Continuation Rule

Continue automatically through available bounded implementation, tests, diagnosis, repair, exact-head qualification, integration, and promotion. Escalate only for a genuine physical/external dependency, authorization/platform boundary, falsified gate, superseded objective, or negative expected value.

This document and `automation/PROJECT_STATE.json` are continuation indexes, not substitutes for source evidence or Git history.
