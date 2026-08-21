# Automation / Frost Forge Source Consolidation

Version: 2.9
Date: 2026-08-21
Canonical repository: `12ephods-source/centinal26`
Canonical production branch: `main`
Source-index snapshot head: `e69a88ebbe15237d96b665bc86951c009d80caf5`

## Purpose

This document removes source-of-truth ambiguity without deleting historical evidence. It classifies repository material into production source, bounded candidates, superseded provenance, external projects, and scientific research branches.

The machine-readable authority for this classification is `automation/SOURCE_INDEX.json`. Deferred work is separately recorded in `automation/DEFERRED_BLOCKERS.json`.

## Production source

Production software is content merged to `main`, except where a gate deliberately pins an older immutable commit. Open branches are never silently treated as production.

Canonical continuation records:

- `AUTOMATION_OS_RUNTIME_CONSOLIDATION.md` — human continuation authority.
- `automation/PROJECT_STATE.json` — machine continuation state.
- `PROJECT_STATE_AUTOMATION_OS.md` — concise continuation record.
- `automation/SOURCE_INDEX.json` — source classification and cleanup authority.
- `automation/DEFERRED_BLOCKERS.json` — blocked-work registry and resume conditions.

Canonical software roots:

- `automation/` — controller, execution, verification, device, deployment, CI, connector, orchestration and agent layers.
- `src/centinal26/` — canonical Centinal26 runtime package.
- `src/frost_core/` — shared Frost runtime primitives.
- `deploy/automation_os/` — universal installer module manager and registry.
- `deploy/termux/` — versioned Android/Termux deployment entry points and compatibility installers.
- `deploy/vercel/` — current Vercel controller deployment target.

## Deferred blockers

Automation uses `DEFER_AND_CONTINUE` for genuine blockers. A blocked item is recorded with its blocker class, evidence, and exact resume condition; it is then skipped while independent eligible work continues.

This policy does not weaken gates. Deferred work cannot be promoted by substitution or inference. In particular, merged host software is not a live external deployment, queued work is not executed work, host/CI evidence is not physical-device evidence, and device validation is not persistence validation.

Current machine-readable deferred state is `automation/DEFERRED_BLOCKERS.json`.

## Installer source

Canonical installer framework:

- `deploy/automation_os/module_manager.py`
- `deploy/automation_os/registry.json`
- `deploy/termux/AUTOMATION_OS_UNIVERSAL_INSTALLER_v3.1.sh`

`AUTOMATION_OS_UNIVERSAL_INSTALLER_v3.0.sh` is retained as compatibility/provenance, not as the preferred entry point.

PR #175 is not an active software source. It is closed and superseded by the current-main reconstruction merged through PR #204.

## Physical-device source

Issue #208 is the canonical physical Android/Termux acceptance tracker.

Qualified commissioning source:

`9c0925ee7e3dc23f6e81718f9c1a2ca7926ec483`

Current acceptance implementation:

- `automation/deployment/enrollment_package/termux_enroll_onepaste.sh`
- `automation/deployment/enrollment_package/verify_physical_commissioning.py`
- `automation/device/heartbeat.py`

Legacy issue #64, RC9, and older finalizer flows are preserved as provenance/compatibility. They are not valid substitutes for issue #208 Phase A/Phase B acceptance.

## Open Automation candidates

The following open PRs are intentionally classified as candidates rather than production: #82, #85, #86, #89, #92, #97, #98, #100, #101, #155, #160, #162, and #164.

This classification does not reject their code. It prevents unmerged branches from being mixed into canonical state. Each candidate must be rebased/reconstructed on current `main`, independently requalified, and merged before it becomes production source.

In particular:

- #86 may contain useful forensic/repository-recovery machinery, but it is not the current physical acceptance authority.
- #97 -> #98 -> #100 form an evidence/Wordbook/chat-bridge candidate stack and remain outside production until deliberately promoted.
- #164 is a Gemini provider candidate; Gemini must not be reported as a production provider merely because the draft exists.

## Superseded/redundant records

Explicit superseded/redundant PRs include:

- #175 — stale installer draft, reconstructed through merged #204.
- #207 — accidental redundant physical-gate tracker.
- #211 — stale state refresh.
- #215 — superseded physical commissioning branch.
- #231 — concurrent state branch that would overwrite newer v2.7 state.

Their history remains useful evidence. They are not current source.

## Repository boundary

This repository also contains work that belongs to other projects. It must not be inferred into Automation production source merely because it shares a Git repository.

External-project examples:

- #128 and #130 — Frost Learning OS.

Scientific/research examples include FToE, KMS/modular, de Sitter, and geometric-symbolic experiment branches. These remain Physics/research lineages unless a separate Automation integration decision explicitly promotes reusable machinery.

## Cleanup rules

1. Never infer production from an open branch.
2. Never infer physical validation from host/CI success.
3. Preserve failed and superseded source history in Git.
4. Keep generated ZIPs, caches, device bundles, and ephemeral validation output out of source control.
5. Retain versioned scripts if an immutable registry, compatibility path, test, or evidence record still references them.
6. Do not duplicate physical-gate trackers; issue #208 is canonical.
7. Connected-service state such as Base44 is coordination/evidence state, not a substitute for canonical software source.
8. File Library artifacts are evidence/source candidates until exact bytes are canonicalized into immutable source.
9. When a work item is genuinely blocked, record it in `automation/DEFERRED_BLOCKERS.json`, preserve its resume condition, skip it, and continue independent work.
10. Never promote a deferred item until the recorded resume condition is independently satisfied.

## Result

After this consolidation, future Automation work should begin from current `main`, read `automation/PROJECT_STATE.json`, `automation/SOURCE_INDEX.json`, and `automation/DEFERRED_BLOCKERS.json`, and treat every other branch as candidate/provenance unless explicitly promoted.
