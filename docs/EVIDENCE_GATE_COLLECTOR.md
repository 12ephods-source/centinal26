# Frost Evidence Gate Collector

Status: host implementation candidate. Physical and external evidence are not implied by merge or CI.

This tool collects the evidence still required by the canonical continuity and Android/Termux gates without adding a second execution plane or weakening issue #208.

## What it collects

1. **Physical commissioning** — runs the existing qualified Android evidence/heartbeat/verifier code from immutable source commit `9c0925ee7e3dc23f6e81718f9c1a2ca7926ec483`, producing a ZIP plus a controller-verification receipt.
2. **Bounded worker evidence** — invokes the existing outbound worker once from the qualified source. The worker remains restricted to its existing allowlisted diagnostic capabilities and signed-job contract.
3. **Encrypted off-device recovery** — encrypts a selected evidence file with `age`, copies the ciphertext to an explicitly configured `rclone` remote, retrieves it, verifies the retrieved ciphertext SHA-256, decrypts the retrieved copy locally, and verifies the recovered plaintext SHA-256. Remote deletion is never automatic.
4. **Reboot return** — records pre-reboot boot identity and enrollment binding, installs a Termux:Boot resume hook, then after a physical reboot requires a changed boot ID, creates a fresh enrollment-bound heartbeat, verifies it, and optionally performs one bounded worker poll.
5. **Synthesis** — `status` reports which evidence classes are actually observed. It never performs release, epistemic, device, or persistence promotion.

## One-paste installation

From Termux:

```bash
curl -fsSL https://raw.githubusercontent.com/12ephods-source/centinal26/main/deploy/termux/FROST_EVIDENCE_GATE_ONE_PASTE_v1.0.sh | bash
```

The installer uses a dedicated checkout under `~/.local/share/frost-evidence-gate/repo`; it does not reset an existing `~/centinal26` worktree. It installs the `frost-evidence-gate` wrapper under `~/bin` and initializes a local `age` identity if one does not already exist in the collector state directory.

## Commands

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

## Evidence semantics

The generated receipts distinguish observation from promotion:

- `commissioning_eligible` means the immutable qualified commissioning verifier passed.
- `bounded_work_observed` means the existing outbound worker returned `PASS` for a real queued allowlisted task.
- `offdevice_recovery_verified` means ciphertext was uploaded, retrieved, hash-matched, decrypted, and plaintext hash-matched.
- `reboot_return_and_work_observed` means boot identity changed, a fresh heartbeat verified, and bounded post-reboot work was observed.
- `device_validated_eligible` and `persistent_validated_eligible` are eligibility summaries only.

The tool deliberately leaves `independent_judge_verified=false`, `lease_event_chain_verified=false`, and `promotion_performed=false`. Those facts must come from the canonical controller/Judge path and cannot be manufactured by the device-side collector.

## Security boundaries

- No arbitrary shell capability is introduced into the worker.
- No remote reboot command is implemented.
- `age` private keys stay local and are chmod `0600` when generated.
- `rclone` credentials are not copied into evidence receipts.
- Symlinks are rejected when packaging commissioning evidence.
- Missing providers, mismatched hashes, stale/invalid heartbeats, unchanged boot IDs, or failed bounded work fail closed.
- Off-device evidence is preserved by default; the collector does not automatically delete the remote ciphertext.
