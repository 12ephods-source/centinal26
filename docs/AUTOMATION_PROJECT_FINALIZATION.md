# Automation Project Finalization

This document defines the current completion boundary for the Centinal26 Automation release line.

## Completion target

The current Automation/Frost Forge host platform is host-verified. Physical Android validation and reboot persistence are separate evidence gates and cannot be inferred from host CI, historical finalizers, issue metadata, or simulation.

Historical RC3/RC4/RC9 and issue-#64 machinery remains preserved as provenance and compatibility material. It is not the current physical acceptance standard unless an explicitly versioned successor decision reinstates it.

## Canonical physical tracker

GitHub issue #208 is the canonical Automation v1 Android/Termux physical qualification tracker. The qualified commissioning source is read from `automation/PROJECT_STATE.json`; do not substitute a moving branch or an older finalizer-only source.

The canonical physical sequence is divided into two promotion layers.

### Phase A — DEVICE_VALIDATED eligibility

1. Run the pinned one-run Android/Termux commissioning package on an authorized real device.
2. Preserve the returned `guardian_physical_validation_<timestamp>.zip` unchanged.
3. Independently verify manifest integrity, exact source commit, Android/Termux origin signals, boot identity, package inventory, normalized device profile, verified enrollment digest, and the heartbeat bound to that enrollment and boot session.
4. Observe/register the same Android worker in the canonical control plane.
5. Dispatch one harmless bounded Android-worker qualification task.
6. Preserve authorization, task/result/evidence digests, lease/event chain, and independent Judge evidence.

A controller result of `VERIFIED_PHYSICAL_COMMISSIONING_ELIGIBLE` establishes commissioning eligibility only. It does not by itself establish successful workload execution or `DEVICE_VALIDATED`.

### Phase B — PERSISTENT_VALIDATED eligibility

After Phase A passes:

1. preserve pre-reboot device/boot/worker/enrollment evidence;
2. physically reboot the phone locally;
3. require a different post-reboot boot ID;
4. require the Termux worker/controller to return;
5. verify a fresh heartbeat bound to the same verified enrollment identity;
6. verify lease, heartbeat, event-chain, and evidence continuity;
7. complete one harmless bounded post-reboot work item;
8. preserve independent Judge evidence.

No automation component is authorized to substitute a remote reboot for the physical reboot observation.

## Historical finalization machinery

The following components may remain in the repository for provenance, historical recovery, compatibility testing, or explicitly authorized legacy reproduction:

- issue #64 release-gate records;
- `automation_project_finalize_v1`;
- `automation_os_physical_ga_rc9_integrity`;
- RC3/RC4/RC9 artifacts and recovery scripts;
- earlier GitHub issue workers and finalizer scripts.

They must not be treated as the default current physical path. The manual `.github/workflows/request-physical-ga.yml` workflow is intentionally guidance-only and reads the current commissioning source from the canonical project state rather than creating a legacy RC9 device job.

## Release promotion

Automatic project completion does not relax validation gates. Release promotion requires evidence appropriate to every active gate and fresh exact-head repository qualification. Maintain at least these distinctions:

- `HOST_VALIDATED`
- `DEVICE_VALIDATED`
- `PERSISTENT_VALIDATED`
- `READY_FOR_GA_PROMOTION`
- `GA`

A later release may impose additional endurance, autonomy, recovery, security, or commercial-readiness gates. Such gates must be versioned and recorded rather than silently imported from a superseded release path.

## Authority boundary

The canonical physical path does not add arbitrary remote shell, caller-selected commands, remote reboot, privilege escalation, or unverified execution. Device-origin evidence, controller verification, bounded execution, and independent verification remain separate stages.
