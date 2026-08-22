# Account Goal Execution Policy

The account-wide controller executes against `GOALS.json` as the canonical goal inventory.

For each cycle:

1. Reconcile current evidence and exact source identities.
2. Recompute goal states conservatively.
3. Rank non-terminal work by expected value, risk reduction, dependency unlocking, information gain, and human-labor reduction.
4. Execute the smallest high-leverage unblocked batch.
5. Independently verify the result and preserve provenance.
6. Adversarially criticize the result and repair verified defects.
7. Reuse existing solution patterns for recurring failure classes before creating new machinery.
8. Consolidate duplicate controllers, watchers, state machines, and artifacts.
9. Continue until all safely actionable work for the cycle is exhausted.

A goal may remain `BLOCKED_EXTERNAL` only after applicable bounded recovery/alternative paths have actually been attempted or shown unavailable. External blocking never authorizes fabricated evidence and never blocks unrelated goals.
