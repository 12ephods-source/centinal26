# Android/Termux persistence qualification

This campaign is the empirical promotion gate from host-qualified code to physical-device and reboot-persistence evidence.

It does not accept a host simulation as physical evidence. The real `prepare` path requires Centinal26's platform identity to report Termux, Android, and an inferred physical device before a device claim can be emitted.

## Promotion semantics

The campaign has two distinct phases.

### Phase 1: physical pre-reboot execution

`bash scripts/device-validation-termux.sh` installs the current checkout into Termux, installs the Centinal26 Termux:Boot hook, records the current kernel `boot_id`, and executes one canonical `system.echo` task through:

`frost-call/1.0 intent.submit -> CanonicalAdapterGateway -> derived-ready task -> authorization denial -> explicit authorization -> bounded execution -> independent verification -> evidence -> task completion`

The campaign requires the unauthorized attempt to stop on `APPROVAL_REQUIRED`. It then performs an explicitly authorized execution and requires the task to reconcile to `COMPLETE`, the event hash chain to verify, the runtime job to be `verified`, the execution evidence to verify, and the runtime audit chain to verify.

A successful Phase 1 establishes `device_validated=true` for that campaign but leaves `persistent_validated=false`. It writes `device-campaign-checkpoint.json` and returns `WAITING_FOR_REBOOT`.

### Phase 2: automatic post-reboot resume

Reboot Android once. The installed `~/.termux/boot/centinal26.sh` hook detects the pending checkpoint and runs the campaign resume path before starting the normal bounded daemon.

Promotion requires all of the following:

- the runtime is still physical Android/Termux;
- `/proc/sys/kernel/random/boot_id` differs from the pre-reboot value;
- the installed Termux:Boot hook path and SHA-256 are unchanged;
- the pre-reboot canonical task, evidence record, event chain, and audit chain still verify;
- a second canonical task passes the same authorization-denial and explicit-authorization gates after reboot;
- the second execution reconciles to `COMPLETE` with verified evidence;
- the final event and runtime audit chains verify;
- the final campaign evidence tree matches its SHA-256 manifest.

Only then is `device-validation-report.json` written with:

- `decision=PERSISTENT_VALIDATED`;
- `device_validated=true`;
- `persistent_validated=true`;
- `autonomous_validated=false`.

This campaign therefore does not claim unattended long-duration autonomy. That remains a separate promotion gate.

## One-command start

From the intended Centinal26 checkout in Termux:

```sh
bash scripts/device-validation-termux.sh
```

After the pre-reboot phase reports PASS, reboot Android once. Termux:Boot performs the post-reboot resume automatically.

After boot, independently inspect the final campaign with:

```sh
python -m centinal26.device_campaign_cli verify \
  --campaign "$HOME/.local/state/centinal26/device-validation/current"
```

The verifier is intentionally read-only. It opens SQLite databases with `mode=ro`, verifies event/evidence/audit hashes without constructing the writable runtime, and may be run repeatedly without changing the evidence it validates.

## Evidence files

The default campaign directory contains the checkpoint, final report, SHA-256 manifest, canonical event database, runtime database, runtime audit chain, and per-execution evidence records. The manifest covers every campaign file except the manifest itself.

If an incomplete or invalid campaign already exists at the default path, the launcher preserves it for diagnosis and refuses to overwrite it. A previously verified campaign is archived before a new campaign is started.

## Evidence boundary

`PERSISTENT_VALIDATED` demonstrates a physical Android/Termux execution before reboot, durable state/evidence survival across a changed kernel boot identity, automatic resume through the installed boot hook, and a second verified canonical execution after reboot.

It does not by itself prove provider/network availability, arbitrary external adapter correctness, long-duration uptime, multiple-reboot reliability, unattended campaigns, or `AUTONOMOUS_VALIDATED`.
