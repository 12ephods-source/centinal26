# Termux Repository Recovery

Status: bounded recovery utility for the Android physical-validation path. It does not grant release, merge, evidentiary-promotion, or package-signature bypass authority.

## Purpose

`termux/termux_repository_recovery.sh` handles a narrow class of Termux package failures before the Centinal26 Android validation campaign runs:

- deprecated or duplicate Termux main repository entries;
- a mixed legacy/current `sources.list` state;
- authenticated `pkg update` failures;
- explicit detection of `NO_PUBKEY 5A897D96E57CF20C` as a missing Termux automatic-build trust anchor rather than a generic mirror failure.

The recovery utility never uses `--allow-unauthenticated`, `trusted=yes`, `apt-key add`, implicit GPG import, or another signature bypass.

## Current upstream reference

The canonical primary Termux main repository is:

```text
deb https://packages.termux.dev/apt/termux-main stable main
```

The current Termux keyring package installs the automatic-build key as `termux-autobuilds.gpg` under the Termux keyring share directory and links it into apt's trusted key directory. Centinal26 checks for that anchor but does not manufacture or silently import it.

## 1. Diagnose without mutation

```bash
cd ~/centinal26
bash termux/termux_repository_recovery.sh --doctor
```

The doctor records active source files, package/keyring state, Termux information when available, the expected automatic-build key ID, and SHA-256 evidence under:

```text
~/.local/state/centinal26/termux-repository-recovery/
```

A clean doctor requires exactly one active Termux main source, that source to be the canonical primary source, no active recognized legacy source, an installed `termux-keyring`, and the `termux-autobuilds.gpg` anchor to be present.

## 2. Repair source configuration

Repository mutation is opt-in:

```bash
export CENTINAL26_ALLOW_PACKAGE_REPAIR=1
bash termux/termux_repository_recovery.sh --repair
```

Before mutation the script captures evidence and copies the existing apt source configuration into a repair-specific `source-backup/` directory. It then disables only recognized active Termux main-source lines, preserves unrelated source entries, appends one canonical primary Termux main source, and attempts an authenticated `pkg update`.

If that update succeeds, the utility refreshes `termux-keyring` and `termux-tools`, runs a second authenticated update, captures the resulting state, and seals the recovery evidence.

## 3. Missing-key boundary

If the authenticated update fails with:

```text
NO_PUBKEY 5A897D96E57CF20C
```

the utility stops with a distinct trust-anchor failure. It does not reinterpret the condition as a mirror problem and does not import a key from the network.

This is intentional. Replacing a repository URL and changing the trusted signing root are different security operations. A missing trust root requires a separately authenticated Termux/keyring recovery path rather than an automatic bypass inside Centinal26.

## 4. Roll back source changes

Each repair records its rollback source snapshot. To restore it:

```bash
export CENTINAL26_ALLOW_PACKAGE_REPAIR=1
bash termux/termux_repository_recovery.sh --rollback \
  ~/.local/state/centinal26/termux-repository-recovery/repair-<timestamp>
```

Rollback itself is captured and SHA-256 sealed.

## Relationship to the physical campaign

Run repository recovery before:

```bash
bash termux/android_forensic_validation_campaign.sh --doctor
```

A passing repository recovery is not Android validation. It only establishes that the local Termux package source and keyring prerequisites are internally coherent enough to continue to the physical Centinal26/Frost Forensics campaign.

The physical campaign remains responsible for pre-reboot evidence acquisition, bounded Centinal26 setup, manual reboot continuity, Termux:Boot evidence, lease recovery, endurance, device sync, independent verification, and the final non-promoting campaign receipt.
