# Automation OS Project State Consolidation

Version: Consolidated Record v2.2
Date: 2026-08-21
Status: HOST_V1_VERIFIED_COMPLETE / PHYSICAL_EVIDENCE_PENDING

## Canonical Continuation Pointers

This file is the concise production-state summary. For continuation and agent routing, use:

- `AUTOMATION_OS_RUNTIME_CONSOLIDATION.md` — canonical human-readable continuation authority.
- `automation/PROJECT_STATE.json` — canonical machine-readable continuation state.
- Git history, exact-head CI evidence, durable workflow ledgers, immutable artifacts, and connector/runtime observations remain primary evidence if summaries diverge.

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
8. PR #203 — physical worker heartbeat activation gate and fail-closed Termux keyring recovery.
9. PR #204 — qualified manifest-driven Automation OS universal Termux installer host software.
10. PR #206 — finalized physical-gate continuation state.
11. PR #205 — autonomous question resolver, action-value decision policy, and append-only decision provenance.

Stale alternatives remain provenance and are not active deployment paths.

## Verified Software State

### Agent/runtime control

- Roles: Planner, Builder, Judge, SRE, Sentinel, Release.
- Reusable agent workflow exposes named profiles rather than arbitrary reusable command input.
- Task and evidence SHA-256 digests are preserved.
- Durable issue #199 records production agent execution state.
- Judge and Sentinel are non-mutating by default.
- Consequential mutations require independent Judge verification.
- Expanded recovery-root operations remain denied.
- Autonomous question resolution ranks authorized alternatives by action value and automatically resolves A0-A2 decisions.
- Exact-authority A3 execution is supported only when the specific side effect is already authorized and platform confirmation permits it.
- A4, authentication, platform-consent, and material-objective-change boundaries remain fail-closed.
- Resolver decisions may be preserved in an append-only JSONL ledger.
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

PR #205 exact-head qualification:
- qualified head `4e603cc44ff559eda6e28cc287665fe3b6bb21ae`;
- CI PASS on Python 3.11, 3.12, and 3.13;
- callable-adapter PASS;
- Automation Validation PASS;
- Executor Integration Validation PASS;
- automation-gates PASS;
- federation-gates PASS;
- validate PASS;
- Mature Product Qualification PASS;
- merged as `8920d6a30f2566299230be70ba26df67400e64da`.

A separate post-merge Actions run for commit `8920d6a30f2566299230be70ba26df67400e64da` has not been observed through the available connector; exact-head qualification remains the supporting evidence.

### Physical-validation software

Current `main` also contains:
- manifest-driven Automation OS Universal Installer v3.1.2;
- profiles including `automation-core-current` and `device-validation`;
- one-paste Termux enrollment/evidence runner;
- fail-closed Android device-origin evidence collector;
- SHA-256 bundle manifest generation;
- controller-side bundle integrity/origin verifier;
- device/boot/enrollment-bound heartbeat protocol and controller verifier;
- fail-closed Termux signing-key recovery for the observed `NO_PUBKEY 5A897D96E57CF20C` environment failure;
- host/tamper/stale/wrong-device/wrong-boot/wrong-enrollment rejection tests.

These software capabilities do not themselves establish physical-device PASS.

### Connected-plugin runtime observation

On 2026-08-21 the ChatGPT plugin permission control rejected global `full_access` as unavailable and accepted `review_important_actions` as the strongest supported global mode observed in this session. This is a platform/runtime observation, not a repository capability or production-connector PASS.

## Release State

DONE / VERIFIED HOST SOFTWARE:
- Automation Platform v1 host/CI vertical slice.
- Durable bounded agent execution and status evidence.
- Bounded authority policy.
- Autonomous question resolution and decision provenance.
- Runtime executor integration.
- Productizer-to-Judge end-to-end verification.
- Universal Android/Termux installer host software.
- Android physical-evidence capture, controller verification, and heartbeat-gate software.

PENDING PHYSICAL EVIDENCE:
- Execute the canonical installer/evidence path on a real authorized Android/Termux device.
- Controller-verify the returned bundle.
- Observe a valid worker heartbeat.
- Execute one bounded Android-worker task and preserve post-execution evidence.

PENDING CONNECTOR AUTHORIZATION / VERIFICATION:
- Production authentication/permission for each external application/service.
- Connector-specific live execution verification.
- Platform review may still apply to important connector actions even where low-risk actions are permitted automatically.

## Core Invariants

- Discovery does not equal authorization.
- Installed software does not equal an active worker.
- Captured evidence does not equal verified enrollment.
- Verified enrollment does not equal active worker heartbeat.
- Execution does not equal success.
- Host/CI PASS does not equal physical-device or production-connector PASS.
- Exact-head qualification does not imply an unobserved post-merge workflow run.
- Absence of acquired evidence is not evidence that the capability or evidence is absent.

## Current Reopening Condition

The next material external gate opens when one authorized physical Android/Termux device executes the canonical deployment/evidence path and returns a generated evidence bundle. The controller verifier must accept that bundle before worker heartbeat or execution promotion. Connector promotion remains service-specific and evidence-gated.
