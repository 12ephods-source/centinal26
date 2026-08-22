# SKY NET v0.1

**Synchronized Knowledge Yield Network for Evidence and Tasks**

SKY NET is a bounded coordination mesh for Automation/Centinal26 and Cybersecurity/Frost Sentinel.

## Invariants

- No arbitrary remote shell.
- Only allowlisted typed jobs.
- Fail closed on dirty or diverged Git state.
- Primary forensic evidence is never copied into the Automation projection.
- Every state-changing job receives an append-only hash-chained audit record.
- HMAC/signature material attests provenance and integrity, not semantic truth.
- Host/software PASS is distinct from Android/Termux physical validation and from scientific/forensic conclusions.

## Initial typed jobs

- `health`
- `verify`
- `project_update`
- `snapshot`

## Termux

From this directory:

```sh
bash install_termux.sh
skynet status
skynet submit health
skynet submit verify
skynet submit project_update
skynet submit snapshot
skynet verify-audit
```

The installer creates a boot-persistent worker that processes only the allowlisted jobs above.
