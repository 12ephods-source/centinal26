# Automation OS / Frost Forge Project Consolidation

Version: 2.5
Status: CANONICAL / HOST_V1_VERIFIED_COMPLETE / PHYSICAL_AND_PERSISTENCE_GATES_EXTERNAL
Repository: `12ephods-source/centinal26`
Canonical branch: `main`
Observed verified production head for this refresh: `32ba85c2d0e0a3a704efcc6a7dd93d7e07809d16`

## Source of Truth

Primary evidence is Git history, exact-head CI, durable workflow ledgers, immutable artifacts, explicit external-gate issues, and the live Base44 physical-gate records. This file is the canonical human continuation authority; `automation/PROJECT_STATE.json` is the machine continuation state; `PROJECT_STATE_AUTOMATION_OS.md` is the concise summary.

## Terminal Objective

Operate a reusable evidence-centered automation platform that converts project intent into bounded execution, independent verification, persistent evidence, reusable capabilities, integrated features, and release candidates while preserving authorization, recovery-root, physical-validation, persistence, provenance, and connector boundaries.

## Canonical Pipeline

`Intent -> Authorization -> Event/Queue -> Capability Selection -> Bounded Execution -> Verification -> Evidence/Audit -> State Update -> Controlled Evolution`

## Verified Host State

Production includes Frost Master Project Protocol v3, deterministic governance, Project Productizer -> Judge E2E validation, Planner/Builder/Judge/SRE/Sentinel/Release execution semantics, bounded authority and recovery-root policy, durable execution evidence, runtime executor contracts, the universal Termux installer, fail-closed module management, exact-source-bound Android evidence capture, controller enrollment verification, the canonical enrollment digest, worker heartbeat generation/verification, and one-run physical commissioning verification.

PR #217 is the current physical-commissioning software baseline. It merged as `32ba85c2d0e0a3a704efcc6a7dd93d7e07809d16` after all exact-head qualification suites passed. The pinned Android run now emits both enrollment evidence and a heartbeat bound to `sha256(MANIFEST.sha256.json)`; `verify_physical_commissioning.py` verifies the returned ZIP end to end.

## Release State

`AUTOMATION_PLATFORM_V1_HOST = VERIFIED_COMPLETE`

`AUTOMATION_PLATFORM_V1_PHYSICAL_DEVICE = BLOCKED_EXTERNAL_PHYSICAL_EVIDENCE`

`AUTOMATION_PLATFORM_V1_PERSISTENCE = BLOCKED_ON_DEVICE_VALIDATED_AND_PHYSICAL_REBOOT`

`AUTOMATION_PLATFORM_V1_EXTERNAL_CONNECTORS = PARTIAL_WITH_MULTIPLE_VERIFIED_SCOPES`

## Physical Gate — Phase A / DEVICE_VALIDATED

Issue #208 is canonical. Qualified commissioning revision: `32ba85c2d0e0a3a704efcc6a7dd93d7e07809d16`.

Current Phase-A sequence:

`one pinned Android/Termux commissioning run -> preserve combined ZIP -> controller end-to-end verification -> observe/register Android worker -> one harmless bounded Android work item -> preserve event/lease chain and independent Judge evidence`

The controller commissioning PASS establishes eligibility, not workload success. Phase A may promote only to `DEVICE_VALIDATED` eligibility after the bounded real-device work item also passes.

## Persistence Gate — Phase B / PERSISTENT_VALIDATED

The older Base44 P1-P5 physical policy is still binding for persistence and is not superseded by the narrower activation gate. After Phase A:

`preserve pre-reboot identity/evidence -> physically reboot phone -> require changed boot_id -> worker/controller returns -> fresh verified heartbeat -> valid lease/event chain -> one harmless post-reboot bounded work item -> independent Judge evidence`

Only Phase B PASS permits `PERSISTENT_VALIDATED` eligibility. Remote reboot is not accepted as physical reboot evidence.

Live Base44 observation at reconciliation: three registered workers, zero Android/Termux workers, zero `AutomationRebootEvidence` rows; P1-P5 remain PENDING and are synchronized to issue #208 and the current physical-validation program.

## Connector Gate

Issue #209 tracks connectors individually.

Verified scopes:
- GitHub: `VERIFIED_LIVE_READ_WRITE` for the authorized Centinal26 repository scope.
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
- physical commissioning eligible != bounded worker task PASS;
- device validated != persistent validated;
- pre-reboot active worker != verified post-reboot worker return;
- captured evidence != verified enrollment != active worker;
- verified enrollment digest != verified heartbeat != successful worker task;
- exact source provenance != device-origin verification;
- reversible write verification != unrestricted connector authority;
- one connector verified != all connectors verified;
- absence of observed evidence != evidence of absence.

## Critical Path

`one-run Android commissioning at 32ba85c... -> controller commissioning verification -> bounded Android worker task -> physical reboot -> verified worker return -> post-reboot bounded task -> remaining connector qualification -> final exact-head release state`

Continue automatically through all available bounded work; stop only at verified completion or a genuine physical/external, authorization/platform, falsification, supersession, or negative-value boundary.
