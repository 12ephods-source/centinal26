# Dedupe/Organizer Device Evidence Contract

This directory defines the repository-side contract for authentic Android/Termux acceptance evidence.

The software release is already host- and repository-qualified. Physical acceptance is a separate gate and MUST NOT be inferred from CI, host simulation, timestamps, filenames, or user prose.

## Required evidence bundle

A device bundle is accepted only when it contains all of the following:

- `acceptance.json`
- `device_profile.txt`
- `self_test.txt`
- `sqlite_integrity.txt`
- `audit_verify.txt`
- `storage_probe.txt`
- `process_restart.txt`
- `boot_probe.txt`
- `SHA256SUMS.txt`

`acceptance.json` must explicitly contain:

```json
{
  "schema_version": "1.0",
  "project": "dedupe-organizer",
  "release": "2.1.0",
  "device_originated": true,
  "android_detected": true,
  "termux_detected": true,
  "boot_id": "<non-empty>",
  "collected_at_utc": "<ISO-8601 UTC>",
  "tests": {
    "self_test": "PASS",
    "sqlite_integrity": "PASS",
    "audit_verify": "PASS",
    "storage_probe": "PASS",
    "process_restart": "PASS",
    "boot_probe": "PASS"
  }
}
```

The verifier checks structure, required PASS states, SHA-256 integrity, Android/Termux provenance fields, and consistency with the v2.1.0 release. It cannot prove cryptographic hardware identity by itself; that remains a limitation unless a separately authenticated device key is introduced.

## Invariant

`host evidence != device evidence`

No CI job is allowed to synthesize `device_originated=true`.