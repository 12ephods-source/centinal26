# Critical-Path Mode

Status: ACTIVE project-governance constraint while P0 physical and external-evidence blockers remain.

## Problem

Centinal26 already has sufficient architecture to attempt its next release milestone. Continued horizontal architecture, feature, research, and evolution work while authentic Android/Termux evidence and missing external forensic evidence remain unresolved creates verification debt without removing the current blockers.

Critical-path mode converts that observation into an enforceable intake rule.

## Current P0 lanes

### A. `physical-ga:#64`

Goal: produce independently verified authentic Android/Termux evidence satisfying the active Issue #64 physical-release contract. Host tests, GitHub Actions, synthetic boot changes, simulations, and session workers do not satisfy this gate.

Permitted work classes:

- `physical-validation`
- `blocker-remediation`
- `security-regression`
- `provenance-recovery`

### B. `external-evidence`

Goal: acquire, authenticate, preserve, ingest, correlate, or explicitly terminally dispose missing original/provider evidence required by the investigation.

Permitted work classes:

- `evidence-acquisition`
- `evidence-recovery`
- `provider-records`
- `blocker-remediation`
- `provenance-recovery`

## Deferred work

While either P0 lane is active, unrelated architecture expansion, controlled evolution, speculative product work, physics/research candidates, Wordbook feature development, new adapters, and optimizations not required by a current blocker are preserved but deferred. A green CI run does not make deferred work release-critical.

## Pull-request contract

A PR targeting `main` must contain these body trailers while critical-path mode is active:

```text
Critical-Path-Class: physical-validation
Critical-Path-Blocker: physical-ga:#64
Critical-Path-Result: sealed authentic Android campaign receipt
```

or another class/blocker combination explicitly allowed by `config/critical_path_policy.json`.

A deliberately frozen PR may carry:

```text
Critical-Path-State: DEFERRED
```

The gate returns exit code `78` for deferred work, intentionally preventing promotion through the critical-path check.

## Trust boundary

The workflow uses `pull_request_target` but checks out the exact trusted base SHA, not candidate code. The PR body is treated only as typed classification data. It cannot widen the allowlist. The policy and evaluator come from the trusted base branch.

The live state of GitHub Issue #64 is refreshed during the workflow. If #64 closes, that single blocker no longer applies, but the external-evidence lane remains active until its gaps receive explicit evidence-backed terminal dispositions.

## Exit rule

Critical-path mode is not disabled merely because time passes or unrelated work is attractive. It exits only through a reviewed, evidence-backed policy/state change after:

1. the physical gate has the required verified device/release disposition; and
2. every external/original evidence gap is either acquired or explicitly classified with a terminal disposition such as `VERIFIED_ABSENT_FROM_SUPPLIED_EXPORT`, `PROVIDER_UNAVAILABLE`, `RETENTION_EXPIRED`, or `IRRECOVERABLE`.

This rule does not require successful attacker attribution. `UNRESOLVED` remains a valid investigation conclusion when available evidence does not discriminate among candidate explanations.
