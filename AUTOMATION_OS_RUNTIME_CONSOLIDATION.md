# Automation OS / Frost Forge Project Consolidation

Version: 2.0
Status: CANONICAL CONSOLIDATION CANDIDATE
Canonical repository: `12ephods-source/centinal26`
Canonical production branch: `main`
Observed production head at consolidation: `5c29afb664a5347f20f642b276ea6ba9a68e2842`

## Source-of-Truth Hierarchy

1. Git history, exact-head CI evidence, and immutable artifacts remain primary evidence.
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
Authorization / Trust Boundary
        |
        v
Executor Registry
  |       |       |       |
 local   repo     API   Android worker
        |
        v
Bounded Agent Execution Plane
Planner / Builder / Judge / SRE / Sentinel
        |
        v
Evidence Generation + Hashing
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
- Operational Planner/Builder/Judge/SRE/Sentinel execution plane.
- Bounded subprocess execution with timeout limits and structured terminal evidence.
- Recovery-root deny boundary in the deployed execution path.
- Task/evidence SHA-256 digests and failure-complete evidence records.
- Event-driven/reusable GitHub Actions agent workflow.
- Runtime executor interface and executor registry.
- Local Python, repository, API connector, Android worker, and canonical agent-plane executor contracts.
- Executor capability metadata and unified request contract.
- Executor integration harness connected to CI.
- Project Productizer -> canonical Protocol v3 provenance binding -> independent Judge verification.
- CI, validate, automation-gates, federation-gates, and Mature Product Qualification.

## Canonical Software Lineage

- PR #174: Project Productizer — MERGED / CANONICAL.
- PR #177: Protocol v2 clean artifacts — MERGED / HISTORICAL CANONICAL.
- PR #181: Protocol v3 — MERGED / ACTIVE CANONICAL CONTROL PLANE.
- PR #187: repository Ruff convergence — MERGED / MAINTENANCE HISTORY.
- PR #190: operational Agent Execution Plane — MERGED / CANONICAL.
- PR #192: event-driven, failure-complete execution — MERGED / CANONICAL.
- PR #193: runtime executor contract unification — MERGED / CANONICAL.
- PR #194: Productizer-to-Judge end-to-end closure — MERGED / CANONICAL.

PR #194 qualified exact head `6ec6ed59ba8c4f9187bc584ba9fe0bb267c03017` with CI, validate, federation-gates, automation-gates, and Mature Product Qualification all PASS. Its merged production lineage is included in `main` before the current production-state record commit.

## Supersession Record

Do not use the following stale deployment paths for new implementation: PR #180, #182, #183, #184, #185, #186, #188, #189, and #191. They are preserved only as failure/reconstruction provenance.

PR #176 is superseded by merged PR #177 and active Protocol v3 PR #181.

## Validation Boundaries

Mandatory distinctions:

- queued != executed != verified;
- installed != authorized;
- executor available != executor verified;
- host/CI PASS != physical-device PASS;
- integration PASS != production external-connector PASS;
- numerical/software consistency != empirical/scientific confirmation;
- evidence existence != accessibility != acquisition != integrity != verification != interpretation;
- absence of observed evidence != evidence of absence.

## Trust / Authority Model

The deployed runtime preserves a narrow recovery-root deny boundary. PR #179 remains an ACTIVE_CANDIDATE because it contains useful authority semantics not yet fully reconciled into the current runtime: explicit role modes, consequential-mutation Judge requirements, expanded recovery-root categories, queue lease, rollback, circuit breaker, and quarantine requirements.

PR #179 should not be merged directly from its stale base. Its useful semantics should be transplanted onto current `main`, independently qualified, then the stale PR should be closed as superseded.

No agent may bypass provider authentication, account/org ownership controls, external authorization, credential recovery controls, or platform-enforced permission boundaries.

## Active Workstreams

### A. Durable Agent Execution Ledger — ACTIVE IMPLEMENTATION

Branch: `feature/agent-execution-ledger-v1`.

Purpose:
- restrict reusable workflow calls to named profiles instead of arbitrary commands;
- retain machine-readable task/evidence/status artifacts;
- maintain a durable GitHub issue status ledger;
- preserve concurrency semantics and final result enforcement.

The branch diverged from current production while v1 closure work landed. Reconstruct its non-superseded value on current `main`; do not merge the stale branch directly.

### B. Agent Authority Policy — ACTIVE CANDIDATE

PR #179. Reconcile its useful semantics into the current runtime on a fresh branch.

### C. Universal Android/Termux Installer — PENDING PHYSICAL VALIDATION

PR #175. Host qualification exists, but physical Android/Termux install/reboot/verify evidence remains a separate gate.

### D. Production Connector Authorization — PARTIAL

Repository/API executor contracts exist. Real third-party connectors require connector-specific authentication, authorization, live execution, and verification evidence.

### E. Real Android Worker Execution — PENDING_PHYSICAL

Android worker contract exists. Enrolled-device execution, manifest, heartbeat, inventory, and post-execution evidence remain pending.

## Release State

`AUTOMATION_PLATFORM_V1_HOST = VERIFIED_COMPLETE`

Verified host/CI scope includes deterministic project productization, canonical Protocol v3 provenance, operational bounded agent execution, independent Judge verification, runtime executor integration, and mature-product host qualification.

`AUTOMATION_PLATFORM_V1_PHYSICAL_DEVICE = PENDING_PHYSICAL`

`AUTOMATION_PLATFORM_V1_EXTERNAL_CONNECTORS = PARTIAL`

Do not collapse these three states into a single global PASS.

## Critical Path

1. Merge this consolidation and make it the continuation authority.
2. Reconstruct the durable Agent Execution Ledger on current main; qualify and merge.
3. Reconcile PR #179 authority semantics into the current execution plane; qualify and merge; close stale #179.
4. Preserve host/CI v1 as a stable baseline and avoid reopening satisfied architecture work without demonstrated regression.
5. Run the Android/Termux physical validation campaign for PR #175 on a real enrolled device.
6. Promote production connector adapters only after connector-specific authorization and execution evidence.

## Stop / Continuation Rule

Continue automatically through available bounded implementation, tests, diagnosis, repair, exact-head qualification, integration, and promotion. Escalate only for a genuine physical/external dependency, authorization/platform boundary, falsified gate, superseded objective, or negative expected value.

This document and `automation/PROJECT_STATE.json` are continuation indexes, not substitutes for source evidence or Git history.
