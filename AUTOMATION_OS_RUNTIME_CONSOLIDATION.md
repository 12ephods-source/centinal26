# Automation OS / Frost Forge Project Consolidation

Version: 2.4
Status: CANONICAL / HOST_V1_VERIFIED_COMPLETE / PHYSICAL_GATE_EXTERNAL
Repository: `12ephods-source/centinal26`
Canonical branch: `main`
Observed verified production head for this refresh: `d6dad40a087140c2efa25eec7eac5ad6f4c7bfd2`

## Source of Truth

Primary evidence is Git history, exact-head CI, durable workflow ledgers, immutable artifacts, and explicit external-gate issues. This file is the canonical human continuation authority; `automation/PROJECT_STATE.json` is the machine continuation state; `PROJECT_STATE_AUTOMATION_OS.md` is the concise summary.

## Terminal Objective

Operate a reusable evidence-centered automation platform that converts project intent into bounded execution, independent verification, persistent evidence, reusable capabilities, integrated features, and release candidates while preserving authorization, recovery-root, physical-validation, provenance, and connector boundaries.

## Canonical Pipeline

`Intent -> Authorization -> Event/Queue -> Capability Selection -> Bounded Execution -> Verification -> Evidence/Audit -> State Update -> Controlled Evolution`

## Control Plane

Frost Master Project Protocol v3 is canonical. Production roles are Planner, Builder, Judge, SRE, Sentinel, and Release. Judge and Sentinel are non-mutating by default; consequential mutations require independent Judge verification; protected recovery-root operations remain denied.

PR #205 adds the autonomous question resolver for resolvable authorized A0-A2 decisions. A4, authorization/platform boundaries, and unknown-data boundaries remain fail-closed.

The production baseline also includes deterministic governance invariants and schemas at commit `d369e0015963dbcf1b336c5d124fac6376fee91e`.

## Verified Host Capabilities

- Project Productizer with Protocol v3 provenance and independent Judge E2E validation.
- Qualified multi-role Agent Execution Plane with durable issue #199 and retained task/evidence artifacts.
- Named bounded reusable workflow profiles instead of arbitrary reusable command input.
- Bounded authority policy, recovery-root deny policy, deterministic governance invariants, and independent Judge gate.
- Runtime executor registry and local/repository/API/Android-worker contracts.
- Manifest-driven universal Android/Termux installer with immutable module registry and fail-closed module manager.
- Android/Termux device evidence capture, SHA-256 manifests, controller verification, and exact source-commit provenance binding.
- Physical worker heartbeat record/controller verifier with device, boot, enrollment-digest, freshness, Android/Termux-signal, and record-hash binding.
- Canonical `enrollment_digest` emitted only after successful controller verification, defined as SHA-256 of verified `MANIFEST.sha256.json`.
- Pinned Termux keyring recovery path.
- Autonomous question resolver for authorized resolvable A0-A2 decisions.

## Canonical Lineage

Active production lineage includes PRs #174, #177, #181, #190, #192, #193, #194, #196, #197, #200, #203, #204, #205, #206, #210, #213, and #214.

PR #213 hardened the physical gate by binding device evidence to the exact executed Centinal26 commit and allowing controller rejection of wrong-revision bundles. All six exact-head qualification suites passed before merge.

PR #214 completed the enrollment-to-heartbeat handoff by emitting the verified manifest SHA-256 as the canonical `enrollment_digest`. All six exact-head qualification suites passed before merge. Production commit: `d6dad40a087140c2efa25eec7eac5ad6f4c7bfd2`.

Superseded alternatives remain provenance only; accidental redundant PR #207 is closed and not part of the active path.

## Durable Evidence

Agent runtime verification after PR #200: run `32488911036`, issue #199, Judge `agent-tests` PASS, 9 tests PASS, task digest `984878fc3193a34e180ae46bdde81d3458fbe139c7043a2c257193a404d05743`, evidence digest `20681ea2c49fbe28f04b70f4c3366ed73c09f40945f0f2f253c5d39f3aea4f76`, artifact #9448948270 digest `sha256:7d2368ec67390701ca1ef589bfe559c5dc69d1a4025714e99c3aaf92a365c9d2`.

External trackers:
- issue #208 — Android/Termux physical qualification gate, pinned to production physical-gate revision `d6dad40a087140c2efa25eec7eac5ad6f4c7bfd2`;
- issue #209 — connector qualification matrix;
- issue #199 — durable agent execution status.

## Release State

`AUTOMATION_PLATFORM_V1_HOST = VERIFIED_COMPLETE`

`AUTOMATION_PLATFORM_V1_PHYSICAL_DEVICE = BLOCKED_EXTERNAL_PHYSICAL_EVIDENCE`

`AUTOMATION_PLATFORM_V1_EXTERNAL_CONNECTORS = PARTIAL_WITH_MULTIPLE_VERIFIED_SCOPES`

## Physical Gate

Issue #208 is canonical and contains the exact immutable one-paste command and controller commands. Remaining facts must originate from one real authorized Android/Termux device:

`pinned device capture -> controller verification against expected commit -> canonical enrollment digest -> fresh heartbeat bound to enrollment + boot session -> controller heartbeat verification -> one harmless bounded Android-worker task -> independent Judge evidence`

Host/CI cannot substitute for these observations. Captured evidence is not verified enrollment; verified enrollment is not an active worker; a verified heartbeat is not a successful worker task.

## Connector Gate

Issue #209 tracks connectors individually.

Verified scopes:
- GitHub: `VERIFIED_LIVE_READ_WRITE` for the currently authorized `12ephods-source/centinal26` repository scope.
- Gmail: `VERIFIED_REVERSIBLE_WRITE` using temporary unsent draft create + cleanup; no mail sent.
- Google Calendar: `VERIFIED_REVERSIBLE_WRITE` using temporary private/transparent event create + delete + absence verification.
- Google Drive: `VERIFIED_REVERSIBLE_WRITE` using temporary native Doc create + metadata readback + permanent delete.
- Google Contacts: `AUTHENTICATED_READ_VERIFIED`.
- Notion: `AUTHENTICATED_READ_VERIFIED`.
- Linear: `AUTHENTICATED_READ_VERIFIED`.

The repository `api_connector_executor` is `VERIFIED_SOFTWARE`; target authorization is separate. Other connectors must cross `ADAPTER_PRESENT -> AUTHENTICATED -> AUTHORIZED -> LIVE_EXECUTED -> INDEPENDENTLY_VERIFIED -> PRODUCTION_QUALIFIED` independently.

## Mandatory Distinctions

- queued != executed != verified;
- installed != authorized;
- host PASS != physical-device PASS;
- captured device evidence != verified enrollment != active worker;
- verified enrollment digest != verified heartbeat != successful worker task;
- exact source provenance != device-origin verification;
- reversible write verification != unrestricted connector authority;
- one connector verified != all connectors verified;
- absence of observed evidence != evidence of absence.

## Critical Path

`real device capture at d6dad40a... -> controller verification -> verified heartbeat -> bounded Android-worker execution -> remaining connector qualification -> final exact-head release state`

Continue automatically through all available bounded work; stop only at verified completion or a genuine physical/external, authorization/platform, falsification, supersession, or negative-value boundary.
