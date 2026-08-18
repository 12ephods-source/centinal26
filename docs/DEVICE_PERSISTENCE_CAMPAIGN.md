# Android/Termux persistence qualification

This campaign is the empirical promotion gate from host-qualified code to physical-device and reboot-persistence evidence.

It does not accept a host simulation as physical evidence. The real `prepare` path requires Centinal26's platform identity to report Termux, Android, and an inferred physical device before a device claim can be emitted.

## Fleet and routing model

Conversations and jobs are **capability-routed**, not handset-pinned. Any available Android/Termux worker may accept work when it satisfies the required capability contract.

The launcher converges the local Termux environment before qualification. If required phone-local commands such as Python, Git, or SHA-256 tooling are missing, it uses Termux `pkg` to install only the missing packages and rechecks the commands before continuing. A phone is not rejected merely because its local Termux package set is incomplete.

A stable `device_id` is retained only for provenance and physical evidence. It identifies which Termux installation actually produced a result; it is not a conversation-routing key.

Each phone uses its own default campaign slot:

`$CENTINAL26_HOME/device-validation/devices/<device_id>/current`

and its own history directory. Therefore an incomplete campaign on Phone A does not block Phone B or Phone C from accepting capability-compatible work or beginning their own physical campaign.

The only same-phone requirement is the reboot proof itself. A pre-reboot persistence campaign must resume on the same Termux identity because otherwise a different handset's boot ID could be misclassified as a reboot. This evidence constraint does **not** prevent the conversation or other jobs from moving to another capable phone; another phone simply uses its own campaign slot.

## Mainline integration boundary

This mainline candidate preserves the canonical Frost installer/runtime introduced after the original stacked persistence PR. It does **not** replace the normal Centinal26 Termux:Boot daemon hook and does not install the repository with editable `pip`.

The physical campaign instead runs directly from one clean Git checkout, records its exact commit SHA in the campaign checkpoint, and installs a dedicated `~/.termux/boot/centinal26-device-campaign.sh` hook. That hook verifies that the checkout still has the recorded SHA and is still clean before it resumes the campaign after reboot.

This keeps the persistence qualification isolated from the normal bounded daemon and avoids silently changing the canonical deployment model.

## Promotion semantics

The campaign has two distinct phases.

### Phase 1: physical pre-reboot execution

`bash scripts/device-validation-termux.sh` first adds any missing Termux package prerequisites, resolves the local persistent `device_id`, selects that phone's campaign slot, verifies a clean Git checkout, records its exact source commit, installs the dedicated campaign boot hook, records the current kernel `boot_id`, and executes one canonical `system.echo` task through:

`frost-call/1.0 intent.submit -> CanonicalAdapterGateway -> derived-ready task -> authorization denial -> explicit authorization -> bounded execution -> independent verification -> evidence -> task completion`

The campaign requires the unauthorized attempt to stop on `APPROVAL_REQUIRED`. It then performs an explicitly authorized execution and requires the task to reconcile to `COMPLETE`, the event hash chain to verify, the runtime job to be `verified`, the execution evidence to verify, and the runtime audit chain to verify.

A successful Phase 1 establishes `device_validated=true` for that campaign but leaves `persistent_validated=false`. It writes `device-campaign-checkpoint.json` plus the device-binding record and returns `WAITING_FOR_REBOOT`.

### Phase 2: automatic post-reboot resume

Reboot the phone that produced Phase 1 evidence once. Termux:Boot runs the dedicated campaign hook. Before resume, the hook requires the same Git commit, a clean checkout, and the same persisted Termux `device_id`. The campaign then requires a changed `/proc/sys/kernel/random/boot_id`, verifies that the campaign boot hook itself is unchanged, re-verifies pre-reboot evidence, and executes a second canonical probe.

Promotion requires all of the following:

- the runtime is still physical Android/Termux;
- the same persisted `device_id` is present for this reboot proof;
- the source checkout is still at the recorded commit and clean;
- `/proc/sys/kernel/random/boot_id` differs from the pre-reboot value;
- the dedicated Termux:Boot campaign hook path and SHA-256 are unchanged;
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

From the intended Centinal26 checkout in Termux on **any** available phone:

```sh
bash scripts/device-validation-termux.sh
```

The launcher installs missing Termux package prerequisites and automatically chooses that phone's local campaign slot. It does not require a conversation to be assigned to that handset.

After the pre-reboot phase reports PASS, reboot that same Android phone once to finish **that phone's** persistence proof. Meanwhile, other phones remain available for other capability-compatible work.

After boot, independently inspect the final campaign by first discovering the local identity and using its campaign slot:

```sh
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
DEVICE_ID="$(python -S -m centinal26.device_campaign_cli identity | python -c 'import json,sys; print(json.load(sys.stdin)["device_id"])')"
python -S -m centinal26.device_campaign_cli verify \
  --campaign "$HOME/.local/state/centinal26/device-validation/devices/$DEVICE_ID/current"
```

The verifier is intentionally read-only with respect to campaign evidence. It opens SQLite databases with `mode=ro&immutable=1`, verifies event/evidence/audit hashes without constructing the writable runtime, and may be run repeatedly without changing the evidence it validates. Device identity state is separate provenance state used to ensure the verifier is evaluating evidence from the same Termux installation.

## Evidence files

Each phone's campaign directory contains the checkpoint, device binding, final report, SHA-256 manifest, canonical event database, runtime database, runtime audit chain, and per-execution evidence records. The manifest covers every campaign file except the manifest itself.

If an incomplete or invalid campaign already exists in **that phone's** default slot, the launcher preserves it for diagnosis and refuses to overwrite it. A previously verified campaign for that phone is archived before a new campaign is started. Campaign state on another phone does not block execution.

## Evidence boundary

`PERSISTENT_VALIDATED` demonstrates a physical Android/Termux execution before reboot, durable state/evidence survival across a changed kernel boot identity on the same persisted Termux identity, automatic resume through a source-pinned dedicated boot hook, and a second verified canonical execution after reboot.

It does not pin conversations or ordinary jobs to a handset. It also does not by itself prove provider/network availability, arbitrary external adapter correctness, long-duration uptime, multiple-reboot reliability, unattended campaigns, hardware attestation, or `AUTONOMOUS_VALIDATED`.
