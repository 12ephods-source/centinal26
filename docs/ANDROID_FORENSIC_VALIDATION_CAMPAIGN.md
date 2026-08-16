# Android + Frost Sentinel Physical Validation Campaign

Status: EXPERIMENTAL integration gate. It does not grant merge, release, attribution, or evidentiary-promotion authority.

## Purpose

This campaign binds the existing Centinal26 Android/Termux physical-validation machinery to Frost Forensics evidence acquisition. It is deliberately a thin orchestration layer: the existing Centinal26 physical gate remains authoritative for controller lifecycle, reboot continuity, lease recovery, heartbeat freshness, endurance, device sync, and independent verification; Frost Forensics remains authoritative for forensic acquisition, integrity audit, resolution, case packaging, and package verification.

The campaign produces a SHA-256-sealed receipt tied to:

- the exact Centinal26 Git commit;
- the pre-reboot and post-reboot Android boot IDs;
- pre- and post-reboot Frost Forensics package hashes;
- the Centinal26 finalization report hash;
- per-step stdout/stderr hashes;
- package/repository diagnostic state.

No raw forensic evidence is uploaded by this wrapper. Existing Centinal26 finalization may post the already-designed endurance-report digest to the configured GitHub issue.

## Safety ordering

The pre-reboot sequence is intentionally:

1. capture package/repository state;
2. run Frost Forensics doctor;
3. acquire bounded non-root Android live state;
4. audit, resolve, package, and independently verify the Frost case package;
5. only then run the existing Centinal26 pre-reboot finalizer, which may create/update its venv, state, and Termux:Boot script;
6. seal the cross-system campaign receipt;
7. require a manual Android reboot.

This ordering captures forensic state before the Centinal26 bootstrap mutates the Termux application data directory.

## Required software

The campaign itself requires Android Termux plus `git`, `python`, `jq`, `sha256sum`, `find`, and `sort`. Frost Forensics v3.1.0 must already expose `frost-forensics`, or `FROST_FORENSICS_BIN` must point to its executable.

Frost Forensics intentionally does not install packages by default on a live evidence device. Preserve that behavior unless the acquisition footprint is explicitly acceptable.

## 1. Preflight

```bash
cd ~/automation-intelligence-control-repo
bash termux/android_forensic_validation_campaign.sh --doctor
```

The doctor records `termux-info`, installed versions of package/keyring tooling, active apt source files, exact repository HEAD, boot ID, required-command presence, and the Frost Forensics executable path.

## 2. Package repair, only if doctor is blocked

The campaign will not bypass apt signature verification. Package mutation requires an explicit opt-in:

```bash
export CENTINAL26_ALLOW_PACKAGE_REPAIR=1
bash termux/android_forensic_validation_campaign.sh --repair-packages
```

If authenticated `pkg update` fails, the script stops and preserves the failure evidence. Use the official `termux-change-repo` utility to select a current mirror, then rerun the repair mode. Do not use `--allow-unauthenticated`, `trusted=yes`, or equivalent signature bypasses.

## 3. Install/locate Frost Forensics

If `frost-forensics` is not already available, install the current Frost Forensics package separately, then verify:

```bash
export PATH="$HOME/.local/bin:$PATH"
frost-forensics --workspace "$HOME/FROST_CASE" doctor
```

The campaign does not vendor or silently replace the Frost Forensics implementation.

## 4. Pre-reboot campaign

```bash
cd ~/automation-intelligence-control-repo
bash termux/android_forensic_validation_campaign.sh --pre-reboot
```

Success is represented by exit code `20` and receipt phase `AWAITING_MANUAL_REBOOT`. The script never reboots the phone itself.

Perform one normal Android reboot after the pre-reboot receipt is sealed.

## 5. Post-reboot campaign

After Termux:Boot has had an opportunity to launch the Centinal26 boot script:

```bash
cd ~/automation-intelligence-control-repo
bash termux/android_forensic_validation_campaign.sh --post-reboot
```

The existing project finalizer requires a changed boot ID, current-boot Termux:Boot evidence, controller return, a fresh heartbeat, event-chain validity, post-reboot work, endurance evidence, device-sync evidence, and independent verification. The campaign then performs a second Frost Android acquisition, integrity audit, resolution, package generation, and package verification.

The campaign passes only when the Centinal26 final report is `READY_FOR_GA_PROMOTION` and the Frost verification steps also pass. The wrapper reports `CAMPAIGN_VALIDATED`; it does not itself promote or merge anything.

## Outputs

Default root:

```text
~/.local/state/centinal26/android-forensic-campaigns/
```

Each campaign contains:

- `steps.jsonl` — machine-readable command receipts;
- `steps/*.stdout` and `steps/*.stderr` — exact captured command streams;
- `package_state_*` — Termux package/repository diagnostics;
- `pre_boot_id` / `post_boot_id`;
- `repo_commit`;
- `PAYLOAD_SHA256SUMS.txt`;
- `campaign_receipt.json`;
- `campaign_receipt.json.sha256`.

A successful campaign also updates `latest_validated_receipt.json`. A failed or interrupted run keeps its evidence directory and does not silently reset the active identity.

## Promotion boundary

`CAMPAIGN_VALIDATED` means the configured device-level mechanics and forensic integration passed for one exact commit and two observed boot epochs. It is not proof of attacker identity, not proof that every source artifact is original, and not an authorization to alter or destroy source evidence. Provider records and explicit authorization review remain separate investigation gates.
