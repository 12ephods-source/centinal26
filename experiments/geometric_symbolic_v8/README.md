# Geometric Symbolic Reasoning v8 — Hidden Symbol Mapping

This is the next gate after PR #152's finite-library structure-selection PASS.

v7 selected the correct exact C4/V4 family from data, but token IDs were already
aligned with the candidate group elements. v8 removes that alignment.

## Hidden-mapping task

For every task/seed, the four observed token IDs are secretly permuted onto the
four group elements before composition. The hidden bijection differs across
runs.

Training excludes length-1 examples and uses only composition chains of lengths
2–5, so the learner cannot recover the token mapping from direct one-token
labels.

Two reciprocal task laws are tested:
- C4 composition;
- V4/Klein-four composition.

Fresh seeds: 60, 61, 62.
Near OOD: 11/12/13.
Far OOD: 61/62/63.

## Candidate hypotheses

The learner sees all 48 exact hypotheses:

`2 algebra families × 24 token→element bijections`.

Each hypothesis deterministically predicts the composed group element. A
trainable categorical posterior is optimized from short-chain data. Training
may use the soft posterior mixture, but final evaluation discards it and uses
one hard argmax hypothesis only.

## Mapping criterion

The selected mapping is not judged merely by literal tuple equality. It must be
**behaviorally equivalent** to the hidden generator on exhaustive sequences of
lengths 2, 3, and 4. This avoids penalizing an equivalent naming convention
while still requiring the selected hypothesis to implement the same observable
composition law.

## Frozen v8 gate

For both C4 and V4 tasks:

- correct algebra family selected in 3/3 seeds;
- behavioral-equivalence rate = 3/3;
- mean posterior on the hard-selected hypothesis > 0.90;
- hard-selected short-chain accuracy > 0.99;
- hard-selected near-OOD pair accuracy > 0.99;
- hard-selected far-OOD pair accuracy > 0.99.

No threshold may change after first CI.

## Interpretation boundary

A PASS would establish joint identification of algebra family and hidden symbol
mapping from composition data within a finite 48-hypothesis library. It would
still not be unrestricted algebra discovery, natural-language reasoning,
Sophontic replication, a 60x efficiency result, or evidence for data-center
obsolescence.
