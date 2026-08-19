# Geometric Symbolic Reasoning v3 — Fresh-Seed Contrastive Replication

## Why v3 exists

Closed PR #142 (v2) produced a formal FAIL because one preregistered negative-control rule required `wrong_pair32 < baseline_pair32 - 0.05`. The exact-head v2 evidence placed baseline pair32 at ~0.003, so that rule required a negative accuracy and was unattainable.

v2 remains frozen as FAIL. This v3 does not edit or reinterpret its checker.

## Degrees of freedom deliberately frozen

v3 imports and executes the exact v2 model, data generator, geometry losses, optimizer, training steps, and evaluation functions from the v2 source already present in the parent branch.

The only execution change is a fresh seed set: `101, 102, 103` instead of v2 seeds `0, 1, 2`.

## Preregistered v3 gate

The negative-control question is now contrastive rather than floor-violating. PASS requires all of:

- mean correct pair32 > baseline pair32 + 0.20;
- mean correct OOD32 > baseline OOD32 + 0.15;
- correct invariant32 >= baseline invariant32 - 0.03;
- mean correct pair32 > wrong pair32 + 0.20;
- mean correct OOD32 > wrong OOD32 + 0.15;
- at least 2 of 3 fresh seeds independently show correct pair32 > baseline + 0.10 and > wrong + 0.10.

These thresholds are frozen before executing the fresh-seed GitHub gate.

## Provenance

Parent v2 exact head: `d49220360c8711a0cda494b809c4c2a0c081d41e`.

v2 evidence artifact digest: `sha256:54488da76be084161634765c058c28c78797d111b45935417eb2477a26868636`.

## Scope

A PASS would establish only that the same toy causal-geometry mechanism replicates on fresh random seeds under a valid contrastive negative control. It would not establish Sophontic's proprietary method, transformer-scale reasoning, 60x efficiency, or data-center obsolescence.
