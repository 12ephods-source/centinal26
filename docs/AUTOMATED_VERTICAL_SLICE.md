# Automated Vertical Slice

The automated runtime implements the canonical operational path:

`Intent → Authorization → Queue → Capability Selection → Bounded Execution → Verification → Evidence → State Update`

`src/centinal26/pipeline.py` is additive to the original core so existing release, qualification, connected-provider, HERMES, and provenance behavior is not silently rewritten.

## Runtime guarantees

- Each intent has a stable ID, canonical SHA-256 identity, and an explicit requested capability.
- Capability grants are checked before enqueue and again before execution.
- SQLite uses WAL mode, a busy timeout, durable states, retry counters, and expiring execution leases.
- Idempotency is content-bound: same key + same immutable intent deduplicates; same key + different intent content raises `IdempotencyConflict` and records an audit event.
- Legacy automation databases are migrated by adding/backfilling the intent hash without discarding existing jobs.
- Expired `running` leases are recovered automatically after interruption.
- Capability execution is time-bounded with POSIX `SIGALRM` when available and an elapsed-time fallback elsewhere.
- The verifier is distinct from the executor; capabilities must explicitly declare verifier independence before the evolution gate can open.
- Every execution attempt gets its own immutable SHA-256 evidence record. Failed attempts are retained rather than overwritten by retries.
- Evidence files are written with temporary-file + flush + `fsync` + atomic replace semantics.
- Canonical state is updated only after verification and evidence-integrity checks pass.
- Canonical state is read back after commit; divergence produces preserved evidence and closes the evolution-readiness gate.
- A state-reducer failure is terminal for that execution attempt and does not automatically replay the already executed capability.

## Automated gate

`bash scripts/host-automation-gate.sh` performs ten clean vertical-slice passes plus a simulated expired-lease recovery pass. The evolution-readiness gate opens only when all of the following are true:

- at least ten consecutive verified runs;
- zero recorded state divergence;
- complete evidence integrity;
- a successful recovery test;
- structurally independent verification.

GitHub Actions executes this gate on pushes, pull requests, manual dispatch, and daily schedule, and preserves generated host evidence as an Actions artifact.

`evolution.ready=true` means only that the defined runtime prerequisites for controlled evolution passed. It is **not** GA promotion, physical Android validation, or permission for unbounded self-modification. Release-control and device-validation gates remain separate and authoritative.

## CLI

```bash
centinal26 auto-demo
centinal26 auto-selftest
centinal26 auto-status
centinal26 auto-run-once
centinal26 auto-daemon --poll 2
```

## Android / Termux

`bash scripts/install-termux.sh` now exercises both the original core and the automated vertical slice during installation.

For opt-in Android boot persistence:

```bash
bash scripts/enable-termux-boot.sh
```

That installs `deploy/termux/centinal26-boot.sh` under Termux:Boot. The hook starts only the bounded allowlisted daemon; it does not create a general remote shell or bypass capability authorization.

## Architectural ownership

This pipeline is shared Automation/Execution machinery. Domain systems such as HERMES, SDOS, AAARD, and project-specific adapters should request typed capabilities through shared execution interfaces rather than cloning queue, retry, verification, or evidence logic.
