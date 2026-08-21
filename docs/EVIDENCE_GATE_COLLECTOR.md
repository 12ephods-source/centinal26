# Frost Evidence Gate Collector

Status: host implementation candidate. Physical and external evidence are not implied by merge or CI.

This tool collects the evidence still required by the canonical continuity and Android/Termux gates without adding a second execution plane or weakening issue #208.

## What it collects

1. **Physical commissioning** — runs the existing qualified Android evidence/heartbeat/verifier code from immutable source commit `9c0925ee7e3dc23f6e81718f9c1a2ca7926ec483`, producing a ZIP plus a controller-verification receipt.
2. **Bounded worker evidence** — invokes the existing outbound worker once from the qualified source. The worker remains restricted to its existing allowlisted diagnostic capabilities and signed-job contract.
3. **Controller-side evidence** — authenticates to the existing Base44 control plane with normal user permissions and exports the matching worker, job, lease, audit chain, result, reboot, physical-gate, work-contract, Judge-role, verification-verdict, and fleet-metric records. It performs no Base44 writes and never uses service-role authority.
4. **Encrypted off-device recovery** — encrypts a selected evidence file with `age`, copies the ciphertext to an explicitly configured `rclone` remote, retrieves it, verifies the retrieved ciphertext SHA-256, decrypts the retrieved copy locally, and verifies the recovered plaintext SHA-256. Remote deletion is never automatic.
5. **Reboot return** — records pre-reboot boot identity and enrollment binding, installs a Termux:Boot resume hook, then after a physical reboot requires a changed boot ID, creates a fresh enrollment-bound heartbeat, verifies it, and optionally performs one bounded worker poll.
6. **Synthesis** — local and controller verifiers report which evidence classes are actually observed. Neither performs release, epistemic, device, or persistence promotion.

## One-paste installation

From Termux:

```bash
curl -fsSL https://raw.githubusercontent.com/12ephods-source/centinal26/main/deploy/termux/FROST_EVIDENCE_GATE_ONE_PASTE_v1.0.sh | bash
```

The installer uses a dedicated checkout under `~/.local/share/frost-evidence-gate/repo`; it does not reset an existing `~/centinal26` worktree. It installs `frost-evidence-gate` and `frost-controller-evidence` under `~/bin`, initializes a local `age` identity if needed, and installs the Base44 SDK only under the collector's private state directory.

## Device and recovery commands

```text
frost-evidence-gate doctor
frost-evidence-gate init-age
frost-evidence-gate commission
frost-evidence-gate worker-once --config /path/to/worker.json
frost-evidence-gate offdevice-roundtrip \
  --source /path/to/guardian_physical_validation_*.zip \
  --identity ~/.local/share/frost-evidence-gate/keys/age-identity.txt \
  --remote remote-name:path/to/evidence
frost-evidence-gate arm-reboot --worker-config /path/to/worker.json
# perform the reboot physically from the Android UI
frost-evidence-gate status
```

`rclone config` is intentionally separate because remote credentials and provider authorization are external secrets. The collector never writes those credentials into receipts.

## Controller evidence commands

The Base44 control plane is queried through the official external SDK with authenticated-user RLS. The wrapper prompts for the account password without echo and passes it to the SDK process over stdin; the password is not placed in command arguments or evidence files.

Phase A example:

```bash
frost-controller-evidence export \
  --worker-instance <ANDROID_WORKER_INSTANCE_ID> \
  --job-id <BOUNDED_JOB_ID> \
  --contract-id <PHYSICAL_WORK_CONTRACT_ID> \
  > ~/.local/share/frost-evidence-gate/controller_phase_a.json

frost-controller-evidence verify \
  ~/.local/share/frost-evidence-gate/controller_phase_a.json \
  --phase phase-a
```

Phase B example after a physical reboot and completed post-reboot bounded job:

```bash
frost-controller-evidence export \
  --worker-instance <ANDROID_WORKER_INSTANCE_ID> \
  --job-id <POST_REBOOT_JOB_ID> \
  --contract-id <PHYSICAL_WORK_CONTRACT_ID> \
  --proposal-key <PHYSICAL_PROPOSAL_KEY> \
  > ~/.local/share/frost-evidence-gate/controller_phase_b.json

frost-controller-evidence verify \
  ~/.local/share/frost-evidence-gate/controller_phase_b.json \
  --phase phase-b
```

The exporter preserves each collection plus a SHA-256 of its canonical JSON and a SHA-256 of the complete bundle. Offline verification recomputes those hashes before evaluating evidence relationships.

### Controller verification semantics

For Phase A, eligibility requires all of the following to be observed in the exported controller records:

- a fresh worker record matching the requested instance and identifying Android/Termux;
- a completed bounded job bound to that worker;
- a lease for that job/worker;
- a valid linked audit chain containing claim and completion/acknowledgement events;
- a successful result bound to the same job and worker;
- the selected work contract;
- an independent `VERIFIED` verdict from `Frost Judge` with a recorded verdict hash.

For Phase B, all Phase A checks remain required, plus a controller `AutomationRebootEvidence` PASS record with different pre/post boot IDs and a successful selected result whose `boot_id` equals the recorded post-reboot boot ID.

`AutomationPhysicalGate`, `AutomationBootSentinel`, Judge-role records, and fleet metrics are preserved for corroboration. A pre-existing physical-gate PASS is reported but is not used as the sole basis for eligibility, avoiding circular validation.

## Evidence semantics

The device-generated receipts distinguish observation from promotion:

- `commissioning_eligible` means the immutable qualified commissioning verifier passed.
- `bounded_work_observed` means the existing outbound worker returned `PASS` for a real queued allowlisted task.
- `offdevice_recovery_verified` means ciphertext was uploaded, retrieved, hash-matched, decrypted, and plaintext hash-matched.
- `reboot_return_and_work_observed` means boot identity changed, a fresh heartbeat verified, and bounded post-reboot work was observed.

The controller verifier separately emits `device_validated_controller_evidence_eligible` and `persistent_validated_controller_evidence_eligible`. These are evidence summaries only; `promotion_performed` remains false. Canonical promotion remains a separate Governor/Judge action.

## Security boundaries

- No arbitrary shell capability is introduced into the worker.
- No remote reboot command is implemented.
- No Base44 create/update/delete or service-role operation exists in the exporter.
- Base44 authentication uses normal user RLS; inaccessible records fail closed rather than bypassing permissions.
- The Base44 password is accepted only through stdin by the exporter wrapper and is not written to receipts.
- `age` private keys stay local and are chmod `0600` when generated.
- `rclone` credentials are not copied into evidence receipts.
- Symlinks are rejected when packaging commissioning evidence.
- Missing providers, mismatched hashes, stale workers, invalid audit chains, absent Judge verdicts, stale/invalid heartbeats, unchanged boot IDs, or failed bounded work fail closed.
- Off-device evidence is preserved by default; the collector does not automatically delete the remote ciphertext.
