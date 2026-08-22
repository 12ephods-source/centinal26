# Dedupe/Organizer v2.1.0

Canonical convergence release for the Dedupe/Organizer project.

The runtime is Android/Termux-first, local-first, provenance-preserving, and non-destructive by default. It combines exact SHA-256 inventory, normalized-text duplicate candidates, immutable typed objects, mandatory provenance for derived objects, hash-chained audit, keyed manifests, bounded events, memory/tasks/baselines/handoffs, explicit reversible quarantine/restore, a read-only localhost bearer-token API, daemon operation, Termux:Boot support, and a device acceptance collector.

## Reconstruct the exact sources

```bash
python tools/dedupe-organizer/materialize.py
python -m py_compile tools/dedupe-organizer/generated/dedupe_organizer.py
python tools/dedupe-organizer/generated/dedupe_organizer.py --root /tmp/dedupe-v2-1 self-test
bash -n tools/dedupe-organizer/generated/device_acceptance.sh
```

Expected SHA-256:

- `dedupe_organizer.py`: `ac8560aa3cb077ca100f204604f2f98ea10bb03c9b7dc6b17c6c10e07d41404f`
- `device_acceptance.sh`: `ddfe6f98d84063c3ee94267b38ddda906442f74ae037abb14613d035e5f59170`

The base64/gzip parts are only an exact transport representation. The materializer refuses to execute a reconstructed source whose SHA-256 differs from the qualified release bytes.

## Release state

`SOFTWARE_COMPLETE_HOST_VALIDATED / DEVICE_ACCEPTANCE_PENDING`

The remaining acceptance gates require authentic Android/Termux evidence: scoped storage, Termux:Boot reboot behavior, process kill/restart, battery/RAM/SQLite endurance, and power-loss recovery. Host or CI evidence must not be promoted as device-origin evidence.
