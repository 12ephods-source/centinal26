# Frost Forge Library Cleaner

A conservative Termux daemon for reclaiming ChatGPT Library upload slots without using private or undocumented provider endpoints.

## Safety model

The cleaner operates only through the already-authenticated Library web UI exposed on the Android device. It fails closed when UI controls are missing or ambiguous.

A Library item is deleted only after all of the following are true:

1. The filename is an exact unique match.
2. The filename is either explicitly allowlisted or matches a configured low-risk cleanup pattern.
3. No denylist pattern matches the filename.
4. The item is downloaded locally.
5. A separate archive copy is written under `~/storage/downloads/FrostForgeLibraryArchive`.
6. SHA-256 of the archive copy is verified.
7. An append-only JSONL ledger entry is written.
8. The exact filename is re-identified immediately before deletion.
9. The confirmation view still exposes the exact filename.
10. A post-delete search no longer finds the exact item.

No coordinate-only blind deletion is permitted.

## Default automatic classes

The default configuration permits only:

- standalone `SHA256SUMS...txt` files;
- `.sha256` sidecars;
- cleanup-generated report/manifest files.

Current/canonical and physical-evidence names are denied by default. Broader version-family pruning is intentionally not enabled because an older version is not automatically expendable evidence.

## One-time Android setup

Android Wireless debugging must be paired once so Termux can use local ADB/UIAutomator:

1. Enable Developer options.
2. Open **Wireless debugging**.
3. Select **Pair device with pairing code**.
4. In Termux run `adb pair <host:pair-port>` and enter the displayed code.
5. Keep the browser signed into the ChatGPT account whose Library is being cleaned.

## Install

From the repository checkout:

```sh
cd deploy/termux/library_cleaner
bash install.sh
```

Then verify behavior before unattended operation:

```sh
python ~/.local/share/frost-library-cleaner/frost_library_cleanerd.py dry-run
python ~/.local/share/frost-library-cleaner/frost_library_cleanerd.py status
```

The runit service is installed at `$PREFIX/var/service/frost-library-cleaner` and a Termux:Boot hook is installed under `~/.termux/boot/`.

## Evidence and rollback

- configuration: `~/.local/share/frost-library-cleaner/config.json`
- state: `~/.local/share/frost-library-cleaner/state.json`
- append-only archive ledger: `~/.local/share/frost-library-cleaner/archive-ledger.jsonl`
- UI snapshots: `~/.local/share/frost-library-cleaner/ui-snapshots/`
- service logs: `~/.local/share/frost-library-cleaner/service-log/`
- archived bytes: `~/storage/downloads/FrostForgeLibraryArchive/`
- evidence bundles: `~/storage/downloads/FrostForgeLibraryCleanerEvidence/`

After a dry-run or real cleanup cycle, package the review evidence with:

```sh
python ~/.local/share/frost-library-cleaner/package_evidence.py
```

The packager creates one ZIP plus a sibling `.sha256` file. By default it includes daemon state, ledger, UI snapshots, service logs, an evidence manifest, and a SHA-256/size index of every locally archived Library item without duplicating the archived bytes into the ZIP. To include those archived bytes too, use:

```sh
python ~/.local/share/frost-library-cleaner/package_evidence.py --include-archived-files
```

Stop the daemon with:

```sh
sv down "$PREFIX/var/service/frost-library-cleaner"
```

Deleted Library items are not restored automatically. The mandatory archive copy and its SHA-256 ledger are the recovery path.

## Provider/UI boundary

The Library deletion surface is a web UI and may change. Any control ambiguity, failed download, failed hash verification, missing exact filename in the confirmation view, or post-delete verification failure stops that item instead of guessing.
