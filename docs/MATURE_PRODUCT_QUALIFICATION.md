# Mature Product Qualification

This repository treats product maturity as a hard-gated evidence state, not a scalar score.

## Host qualification

The `Mature Product Qualification` workflow runs:

1. package installation;
2. Ruff;
3. the full pytest suite;
4. repository invariant validation;
5. host rollback ancestry verification;
6. `scripts/mature_product_gate.py`.

Without physical evidence the expected result is `BLOCKED_EXTERNAL`, not `MATURE` and not a failure of the host implementation.

## Physical qualification

A physical evidence record may satisfy the hard device gate only when all of the following are true:

- `platform == android/termux`;
- a fresh worker heartbeat is observed;
- an existing bounded job is actually completed on that worker;
- its result is independently verified;
- a forbidden/unsupported capability is rejected;
- `post_boot_id != pre_boot_id` after a real Android reboot;
- the same worker lineage returns with a fresh post-reboot heartbeat;
- the configured endurance campaign passes.

`termux/mature_product_probe.sh` captures the pre-reboot boot identity and creates a fail-closed evidence template. It deliberately initializes all runtime claims to `false`; they must be populated from real worker/device evidence rather than manually asserted without provenance.

## Decision rule

`MATURE` requires every host and physical hard gate to pass. Performance, fitness, or aggregate scores cannot compensate for a failed constitutional gate.
