# Automation OS Project State Consolidation

Version: Consolidated Record v2.1
Date: 2026-08-21
Status: HOST_V1_VERIFIED_COMPLETE / PHYSICAL_EVIDENCE_PENDING

## Canonical Continuation Pointers

This file is the concise production-state summary. For continuation and agent routing, use:

- `AUTOMATION_OS_RUNTIME_CONSOLIDATION.md` — canonical human-readable continuation authority.
- `automation/PROJECT_STATE.json` — canonical machine-readable continuation state.
- Git history, exact-head CI evidence, durable workflow ledgers, and immutable artifacts remain primary evidence if summaries diverge.

## Objective

Operate an evidence-first automation platform connecting project requirements, qualified agents, bounded authority, capabilities, execution, independent verification, productization, device workers, connectors, and auditable evidence.

## Canonical Software Lineage

The active Automation Platform v1 lineage includes:

1. PR #190 — bounded Planner/Builder/Judge/SRE/Sentinel execution plane.
2. PR #192 — event-driven, failure-complete execution.
3. PR #193 — normalized runtime executor contracts and executor integration.
4. PR #194 — Productizer -> Protocol v3 provenance -> Judge end-to-end closure.
5. PR #196 — canonical continuation-state consolidation.
6. PR #197 — durable bounded agent execution ledger and named workflow profiles.
7. PR #200 — current-runtime authority policy reconciliation and Release role semantics.

Stale alternatives remain provenance and are not active deployment paths.

## Verified Software State

### Agent/runtime control

- Roles: Planner, Builder, Judge, SRE, Sentinel, Release.
- Reusable agent workflow exposes named profiles rather than arbitrary reusable command input.
- Task and evidence SHA-256 digests are preserved.
- Durable issue #199 records the latest production agent execution state.
- Judge and Sentinel are non-mutating by default.
- Consequential mutations require independent Judge verification.
- Expanded recovery-root operations remain denied.
- Provider authentication, credential recovery, account ownership, and third-party authorization remain external boundaries.

### Production verification

PR #197 production push verification:
- merge commit `fc1cb13696099e5cf32f43f55f7c1fc8868a31d0`;
- Judge `agent-tests` PASS;
- durable issue #199 created;
- machine evidence artifact retained.

PR #200 production push verification:
- merge commit `883673d8ae03be09d0db0cc646e9a0c7b4ab692a`;
- run `32488911036`;
- Judge `agent-tests` PASS;
- 9 tests PASS;
- evidence artifact #9448948270 retained with SHA-256 digest.

### Physical-validation software

Current `main` also contains:
- one-paste Termux enrollment/evidence runner;
- fail-closed Android device-origin evidence collector;
- SHA-256 bundle manifest generation;
- controller-side bundle integrity/origin verifier;
- host/tamper rejection tests.

These software capabilities do not themselves establish physical-device PASS.

## Release State

DONE / VERIFIED HOST SOFTWARE:
- Automation Platform v1 host/CI vertical slice.
- Durable bounded agent execution and status evidence.
- Bounded authority policy.
- Runtime executor integration.
- Productizer-to-Judge end-to-end verification.
- Android physical-evidence capture and controller-verification software.

PENDING PHYSICAL EVIDENCE:
- Execute enrollment/evidence capture on a real authorized Android/Termux device.
- Controller-verify the returned bundle.
- Observe a valid worker heartbeat.
- Execute one bounded Android-worker task and preserve post-execution evidence.

PENDING CONNECTOR AUTHORIZATION:
- Production authentication/permission for each external application/service.
- Connector-specific live execution verification.

## Core Invariants

- Discovery does not equal authorization.
- Installed software does not equal an active worker.
- Captured evidence does not equal verified enrollment.
- Verified enrollment does not equal active worker heartbeat.
- Execution does not equal success.
- Host/CI PASS does not equal physical-device or production-connector PASS.
- Absence of acquired evidence is not evidence that the capability or evidence is absent.

## Current Reopening Condition

The next material external gate opens when one authorized physical Android/Termux device executes `automation/deployment/enrollment_package/termux_enroll_onepaste.sh` and returns the generated evidence bundle. The controller verifier must accept that bundle before worker heartbeat or execution promotion.
