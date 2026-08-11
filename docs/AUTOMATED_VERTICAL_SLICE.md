# Automated Vertical Slice

The automated runtime implements the canonical operational path:

`Intent → Authorization → Queue → Capability Selection → Bounded Execution → Verification → Evidence → State Update`

`src/centinal26/pipeline.py` is additive to the original core so historical release and provenance behavior is not silently rewritten.

## Runtime guarantees

- Each intent has a stable ID and an explicit requested capability.
- Capability grants are checked before enqueue and again before execution.
- SQLite uses WAL mode, a busy timeout, unique idempotency keys, durable states, retry counters, and expiring execution leases.
- Expired `running` leases are recovered automatically after interruption.
- Capability execution is time-bounded with POSIX `SIGALRM` when available and an elapsed-time fallback elsewhere.
- The verifier is a distinct function from the executor; capabilities must explicitly declare verifier independence before the evolution gate can open.
- Every execution attempt gets its own immutable SHA-256 evidence record. Failed attempts are retained rather than overwritten by retries.
- Canonical state is updated only after verification and evidence-integrity checks pass.
- A state-reducer failure is terminal for that execution attempt and does not automatically replay the capability, avoiding duplicate external side effects.

## Automated gate

`bash scripts/host-automation-gate.sh` performs ten clean vertical-slice passes plus a simulated expired-lease recovery pass. The evolution-readiness gate opens only when all of the following are true:

- at least ten consecutive verified runs;
- zero recorded state divergence;
- complete evidence integrity;
- a successful recovery test;
- structurally independent verification.

GitHub Actions executes this gate on pushes, pull requests, manual dispatch, and daily schedule, and preserves the generated host evidence as an Actions artifact.

`evolution.ready=true` means the runtime prerequisites for controlled evolution passed. It is **not** GA promotion, physical Android validation, or permission for unbounded self-modification. Release-control and device-validation gates remain separate and authoritative.

## CLI

```bash
centinal26 auto-demo
centinal26 auto-selftest
centinal26 auto-status
centinal26 auto-run-once
centinal26 auto-daemon --poll 2
```

For Android boot persistence, `bash scripts/enable-termux-boot.sh` installs an opt-in Termux:Boot hook. The hook only starts the allowlisted bounded daemon; it does not create an unrestricted remote shell.

© 2026 Robert Frost
