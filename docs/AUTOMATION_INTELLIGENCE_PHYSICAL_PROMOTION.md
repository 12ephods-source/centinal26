# Automation Intelligence Controller — Physical Android Promotion

This layer turns host-qualified Automation/Frost Forge code into falsifiable Android/Termux device and persistence gates.

## Canonical authority

GitHub issue #208 and `automation/PROJECT_STATE.json` define the current physical-validation lineage. Historical issue #64 workers/finalizers and RC-era commands remain provenance/compatibility material and are not the default current acceptance path.

## Phase A — DEVICE_VALIDATED eligibility

1. Resolve the immutable qualified commissioning source from canonical project state.
2. Run the one-run commissioning entry point on a real authorized Android/Termux device.
3. Preserve the returned ZIP before interpretation or remediation.
4. On the controller, verify SHA-256 manifest integrity and exact source-commit provenance.
5. Verify Android/Termux origin signals, boot identity, package inventory, and normalized device profile.
6. Verify the canonical enrollment digest and heartbeat bound to the same device, enrollment, and boot session.
7. Observe/register that same Android worker in the canonical control plane.
8. Execute one harmless bounded Android-worker qualification task.
9. Preserve task/result/evidence digests, lease/event continuity, and independent Judge evidence.

Commissioning eligibility alone is not a successful worker task and is not `DEVICE_VALIDATED` by itself.

## Phase B — PERSISTENT_VALIDATED eligibility

After Phase A passes:

1. preserve the pre-reboot boot ID, worker identity, enrollment digest, heartbeat, task digest, and evidence digest;
2. physically reboot the Android device locally;
3. require a changed boot ID;
4. require the Termux worker/controller to return;
5. verify a fresh heartbeat bound to the same enrollment identity;
6. verify lease, heartbeat, event-chain, and evidence continuity;
7. execute one harmless bounded post-reboot work item;
8. preserve independent Judge evidence.

The scripts and controllers must never treat remote reboot, host execution, GitHub Actions, session workers, simulation, stale evidence, or evidence from a different phone as physical persistence proof.

## Manual GitHub workflow

`.github/workflows/request-physical-ga.yml` is guidance-only. It reads the current commissioning source and tracker from `automation/PROJECT_STATE.json` and publishes the exact phone-side command to the workflow summary. It does not enqueue, claim, or execute a physical device job.

## Historical compatibility

Earlier issue workers and finalization scripts may remain to preserve reproducibility and historical evidence. Their presence does not make them current. In particular, `automation_os_physical_ga_rc9_integrity`, `automation_project_finalize_v1`, and older issue-#64 paths must not be used to promote the current physical state unless an explicit versioned policy decision reactivates them.

## State and evidence

Host CI proves host/software qualification only. Device capture, controller-verified commissioning, bounded worker execution, reboot persistence, and release promotion are separate states. The controller should retain normalized device facts such as manufacturer, model, Android version, architecture, kernel, Termux version, and termux-tools version as provenance fields; those descriptive fields do not independently authorize or promote the device.
