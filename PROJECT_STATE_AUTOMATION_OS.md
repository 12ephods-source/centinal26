# Automation OS Project State Consolidation

Version: Consolidated Record v2.7
Date: 2026-08-21
Status: HOST_V1_VERIFIED_COMPLETE / RUNTIME_GOVERNANCE_ENFORCED / DEVICE_AND_PERSISTENCE_GATES_EXTERNAL / MULTIPLE_CONNECTOR_SCOPES_VERIFIED

Canonical records: `AUTOMATION_OS_RUNTIME_CONSOLIDATION.md` and `automation/PROJECT_STATE.json`. Git history, exact-head CI, durable ledgers, immutable artifacts, external-gate issues, and live Base44 gate records remain primary evidence.

Observed production head before this refresh: `e36ddbafec46d0a5d7da29b40633db5476a34a48`.
Runtime-governance exact-head validation source: `427f8e884352839e11fcd99cfcdd51643fb1f2ab`.
Qualified physical-commissioning source: `9c0925ee7e3dc23f6e81718f9c1a2ca7926ec483`.

## Verified Host State

Production includes Protocol v3, deterministic governance, Productizer -> Judge E2E validation, the bounded multi-role execution plane, durable evidence, reconciled executor contracts, the universal Termux installer, exact source provenance for Android evidence, normalized Android/Termux device-profile capture, canonical verified enrollment digest, worker heartbeat verification, the one-run physical commissioning package/controller verifier, and the Vercel durable-controller bootstrap.

Recent reconciliations:
- PR #222 / `ea6195aee431a134985f0b02429f1855a4f93adb`: Protocol v3 canonical status and exact response envelope fixed and regression-tested.
- PR #225 / `9c0925ee7e3dc23f6e81718f9c1a2ca7926ec483`: canonical Android commissioning hardening, normalized device profile, issue-#208 documentation, RC9 normal trigger retired.
- PR #226 / `73859661e4104f392f6ad197ab5aa3ba6fb20246`: executor-registry verification state reconciled; Android remains physical-pending.
- PR #227 / `e36ddbafec46d0a5d7da29b40633db5476a34a48`: Vercel first-party durable controller bootstrap; live deployment remains authorization/token dependent.

## Release State

`AUTOMATION_PLATFORM_V1_HOST = VERIFIED_COMPLETE`

`AUTOMATION_PLATFORM_V1_RUNTIME_GOVERNANCE = VERIFIED_COMPLETE_HOST`

`AUTOMATION_PLATFORM_V1_PHYSICAL_DEVICE = BLOCKED_EXTERNAL_PHYSICAL_EVIDENCE`

`AUTOMATION_PLATFORM_V1_PERSISTENCE = BLOCKED_ON_DEVICE_VALIDATED_AND_PHYSICAL_REBOOT`

`AUTOMATION_PLATFORM_V1_EXTERNAL_CONNECTORS = PARTIAL_WITH_MULTIPLE_VERIFIED_SCOPES`

## Phase A — DEVICE_VALIDATED

Issue #208 is canonical. Current commissioning source: `9c0925ee7e3dc23f6e81718f9c1a2ca7926ec483`.

`one pinned Android commissioning run -> preserve combined ZIP -> controller end-to-end verification -> normalized device-profile consistency -> register/observe Android worker -> one bounded Android worker task -> independent Judge evidence`

The user-supplied comparison profile currently reports Samsung `SM-A155M`, Android 16, aarch64, Termux `googleplay.2026.06.21`, termux-tools 3.0.9, and kernel `6.12.38-android16-5-abA155MUBSBEZG1-4k`. It remains user-supplied/unverified until reproduced in the source-bound device bundle and controller-verified.

A commissioning PASS alone does not imply the bounded worker task passed.

## Phase B — PERSISTENT_VALIDATED

`preserve pre-reboot evidence -> physical reboot -> changed boot_id -> worker return -> fresh verified heartbeat -> valid lease/event chain -> one bounded post-reboot work item -> independent Judge evidence`

Phase A PASS permits `DEVICE_VALIDATED` eligibility. Phase B PASS permits `PERSISTENT_VALIDATED` eligibility. No stage skipping.

Legacy issue #64/RC9/finalizer paths are provenance/compatibility only, not the current acceptance path.

## Connector Gate

Issue #209 tracks connectors individually.

- GitHub: `VERIFIED_LIVE_READ_WRITE` for the authorized Centinal26 scope.
- Base44: `VERIFIED_LIVE_READ_WRITE` for the authorized Automation entity scope.
- Gmail: `VERIFIED_REVERSIBLE_LIVE_WRITE` for the tested bounded path.
- Google Calendar: `VERIFIED_REVERSIBLE_LIVE_WRITE`.
- Google Drive: `VERIFIED_REVERSIBLE_LIVE_WRITE`.
- Google Contacts: `AUTHENTICATED_READ_VERIFIED_WRITE_SURFACE_UNAVAILABLE`.
- Notion: `AUTHENTICATED_READ_VERIFIED`.
- Linear: `AUTHENTICATED_READ_VERIFIED`.

Qualification remains operation- and scope-specific. No connector-wide unrestricted authority is inferred.

## Automation Topology

One canonical physical watcher remains active: `6a88614d12e8819183a02d32288b5f10`. The duplicate physical watcher `6a886b66af108191ab79637891732a39` is paused. The retained watcher resolves the current physical source from canonical machine state.

## Core Invariants

- installed != authorized;
- queued != executed != verified;
- host PASS != physical-device PASS;
- objective proposal != authorized objective;
- Judge verification != objective authorization != capability-token scope;
- commissioning eligible != successful bounded worker task;
- device validated != persistent validated;
- descriptive device profile != authorization or physical PASS;
- reversible write verification != unrestricted connector authority;
- one connector verified != all connectors verified;
- absence of observed evidence != evidence of absence.

## Critical Path

`one-run Android commissioning at 9c0925e... -> controller verification -> bounded Android task -> DEVICE_VALIDATED -> physical reboot -> verified return -> post-reboot bounded task -> PERSISTENT_VALIDATED -> final evidence-gated promotion decision`
