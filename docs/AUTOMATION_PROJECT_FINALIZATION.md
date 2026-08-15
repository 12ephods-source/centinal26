# Automation Project Finalization

This document defines the completion boundary for the current Centinal26 Automation release line.

## Completion target

The current product release target is `1.0.0` on the event-kernel-based Centinal26 runtime. The historical RC3/RC4 reconstruction lineage remains preserved as provenance and recovery evidence, but it no longer controls the current product release decision.

This separation is intentional:

- historical RC4 recovery asks whether exact earlier parent artifacts can be recovered and reconstructed faithfully;
- current Centinal26 qualification asks whether the present runtime is safe, bounded, persistent, recoverable, and operational on the real Android/Termux execution node.

A missing historical artifact must remain reported as missing. It does not become reconstructed provenance, but it also does not invalidate a separately verified current implementation.

## Single physical finalization path

GitHub issue #64 is the single current physical release gate. The Android worker accepts only `automation.github_job/v2` with command `automation_project_finalize_v1`.

The pre-reboot phase performs:

1. best-effort exact RC4 parent recovery for historical provenance only;
2. real Android/Termux runtime check;
3. local controller work claim and completion;
4. expired-lease recovery;
5. heartbeat advancement;
6. event-chain validation;
7. preparation of transparent Termux:Boot hooks.

It then stops at `AWAITING_REBOOT`. No component is authorized to reboot the phone remotely.

After the user physically reboots the Android device, the post-reboot phase proves:

1. boot identity changed;
2. Termux:Boot returned the controller/node;
3. heartbeat is fresh;
4. post-reboot work completes;
5. the event chain remains valid;
6. an unsupported worker command is rejected fail-closed;
7. a bounded watchdog recovery drill succeeds;
8. 61 healthy samples over at least 3500 seconds complete on one boot;
9. the device publishes a bounded evidence comment to the active GitHub issue;
10. a separate Python verifier recomputes the release decision from raw evidence and hashes.

Only then may the physical issue close and the control plane proceed to GA promotion.

## Automatic GA promotion

The user has authorized automatic project completion. That authorization does not relax any validation gate.

After independently verified physical evidence is observed, the Automation Intelligence Controller may automatically prepare and merge the final release metadata only when the exact candidate head passes all repository qualification gates and no authority boundary has widened.

The release controller must preserve the distinction between:

- `HOST_VALIDATED`
- `PHYSICAL_VALIDATED`
- `READY_FOR_GA_PROMOTION`
- `GA`

## Historical RC4 provenance

`deploy/termux/recover-rc4-parent-inputs.sh` remains preserved. The physical finalizer attempts it opportunistically and records its report. A successful recovery improves historical provenance. A missing exact parent remains an explicit historical gap.

Historical RC4 recovery is not a current Centinal26 GA gate.

## GitHub Pages

The repository website is optional operator UI. GitHub Pages deployment currently requires repository-owner enablement that the connected GitHub App cannot grant. This permission boundary does not block the runtime release. The site source remains preserved, and `deploy/termux/serve-site.sh` remains a local fallback.

## Authority boundary

The finalization path does not add arbitrary remote shell, caller-selected commands, remote reboot, privilege escalation, or unverified execution. GitHub issues remain proposal/transport records; the physical worker executes one fixed semantic finalization command.
