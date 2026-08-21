# Automation OS / Frost Forge Project Consolidation

Version: 2.3
Status: CANONICAL / HOST_V1_VERIFIED_COMPLETE / PHYSICAL_GATE_EXTERNAL
Repository: `12ephods-source/centinal26`
Canonical branch: `main`
Observed verified host production head before this state PR: `8920d6a30f2566299230be70ba26df67400e64da`

## Source of Truth

Primary evidence is Git history, exact-head CI, durable workflow ledgers, immutable artifacts, and explicit external-gate issues. This file is the canonical human continuation authority; `automation/PROJECT_STATE.json` is the machine continuation state; `PROJECT_STATE_AUTOMATION_OS.md` is the concise summary.

## Terminal Objective

Operate a reusable evidence-centered automation platform that converts project intent into bounded execution, independent verification, persistent evidence, reusable capabilities, integrated features, and release candidates while preserving authorization, recovery-root, physical-validation, and connector boundaries.

## Canonical Pipeline

`Intent -> Authorization -> Event/Queue -> Capability Selection -> Bounded Execution -> Verification -> Evidence/Audit -> State Update -> Controlled Evolution`

## Control Plane

Frost Master Project Protocol v3 is canonical. Production roles are Planner, Builder, Judge, SRE, Sentinel, and Release. Judge and Sentinel are non-mutating by default; consequential mutations require independent Judge verification; protected recovery-root operations remain denied.

PR #205 adds the autonomous question resolver as a deterministic runtime policy for resolvable authorized A0-A2 decisions. Its exact head `4e603cc44ff559eda6e28cc287665fe3b6bb21ae` passed CI, Automation Validation, Executor Integration Validation, validate, automation-gates, federation-gates, and Mature Product Qualification. A4, authorization/platform boundaries, and unknown-data boundaries remain fail-closed.

## Verified Host Capabilities

- Project Productizer with Protocol v3 provenance and independent Judge E2E validation.
- Qualified multi-role Agent Execution Plane with durable issue #199 and retained task/evidence artifacts.
- Named bounded reusable workflow profiles instead of arbitrary reusable command input.
- Bounded authority policy, expanded recovery-root deny policy, and independent Judge gate.
- Runtime executor registry and local/repository/API/Android-worker contracts.
- Manifest-driven universal Android/Termux installer with immutable module registry and fail-closed module manager.
- Android/Termux device evidence capture, SHA-256 manifests, and controller-side device evidence verification.
- Physical worker heartbeat record software and controller verifier with device, boot, enrollment-digest, freshness, Android/Termux-signal, and record-hash binding.
- Pinned Termux keyring recovery path.
- Autonomous question resolver for authorized resolvable A0-A2 decisions.

## Canonical Lineage

PRs #174, #177, #181, #190, #192, #193, #194, #196, #197, #200, #203, #204, #205, and #206 form the active production lineage. PRs #175, #176, #179, #180, #182, #183, #184, #185, #186, #188, #189, #191, and accidental redundant #207 are superseded provenance only.

## Durable Evidence

Agent runtime verification after PR #200: run `32488911036`, issue #199, Judge `agent-tests` PASS, 9 tests PASS, task digest `984878fc3193a34e180ae46bdde81d3458fbe139c7043a2c257193a404d05743`, evidence digest `20681ea2c49fbe28f04b70f4c3366ed73c09f40945f0f2f253c5d39f3aea4f76`, artifact #9448948270 digest `sha256:7d2368ec67390701ca1ef589bfe559c5dc69d1a4025714e99c3aaf92a365c9d2`.

External trackers:
- issue #208 — Android/Termux physical qualification gate;
- issue #209 — connector qualification matrix;
- issue #199 — durable agent execution status.

## Release State

`AUTOMATION_PLATFORM_V1_HOST = VERIFIED_COMPLETE`

`AUTOMATION_PLATFORM_V1_PHYSICAL_DEVICE = BLOCKED_EXTERNAL_PHYSICAL_EVIDENCE`

`AUTOMATION_PLATFORM_V1_EXTERNAL_CONNECTORS = PARTIAL_WITH_GITHUB_VERIFIED`

## Physical Gate

Issue #208 is the canonical tracker. Remaining facts must originate from a real authorized Android/Termux device: run the current enrollment/evidence path, preserve the bundle, controller-verify hashes/origin/boot/inventory/enrollment, emit and verify heartbeat bound to the enrollment digest and boot session, execute one harmless bounded Android-worker task, and preserve independent Judge evidence. Host/CI cannot substitute for these observations.

## Connector Gate

Issue #209 tracks connectors individually. The live GitHub connector is `VERIFIED_LIVE_READ_WRITE` for the currently authorized `12ephods-source/centinal26` scope. The repository `api_connector_executor` is `VERIFIED_SOFTWARE`; target authorization is separate. Other connectors must cross `ADAPTER_PRESENT -> AUTHENTICATED -> AUTHORIZED -> LIVE_EXECUTED -> INDEPENDENTLY_VERIFIED -> PRODUCTION_QUALIFIED` independently.

## Mandatory Distinctions

- queued != executed != verified;
- installed != authorized;
- host PASS != physical-device PASS;
- captured device evidence != verified enrollment != active worker;
- heartbeat software verified != real-device heartbeat observed;
- one connector verified != all connectors verified;
- absence of observed evidence != evidence of absence.

## Critical Path

`real device capture -> controller verification -> verified heartbeat -> bounded Android-worker execution -> remaining connector qualification -> final exact-head release state`

Continue automatically through all available bounded work; stop only at verified completion or a genuine physical/external, authorization/platform, falsification, supersession, or negative-value boundary.
