# Geometric Symbolic Reasoning v7 — Data-Driven Structure Selection

This is the first successor after PR #151's structurally exact reference PASS.

PR #151 established that an explicitly supplied exact C4 algebra gives perfect
long-horizon generalization on the toy C4 task, while exact V4, generic fixed,
and independent SO(4) controls do not. It did **not** establish that a learner
can infer which algebra is correct.

## v7 question

Can training data select the correct exact structural hypothesis from a finite
candidate library, with final evaluation performed on one hard-selected family
rather than on a soft ensemble?

## Candidate library

- exact C4 regular representation;
- exact V4/Klein-four regular representation;
- generic fixed non-group orthogonal permutations;
- four unrelated learned SO(4) operators.

Each candidate has its own learnable latent basis/start/head. Candidates are
warmed equally before selector optimization to reduce initialization races.
A trainable categorical selector then mixes candidate logits during selection
training with entropy pressure toward a single hypothesis.

Final evaluation discards the mixture and uses only `argmax(selector)`.

## Reciprocal control

Two task laws are trained independently:

1. C4 target: sequence sum modulo four.
2. V4 target: sequence XOR under two-bit Klein-four composition.

The C4 task must hard-select C4. The V4 control task must hard-select V4. Thus a
fixed architectural preference for C4 cannot satisfy the complete gate.

Fresh seeds: 50, 51, 52.
Training lengths: 1–4.
Near OOD: 11/12/13.
Far OOD: 61/62/63.

## Frozen v7 gate

For **both** C4 and V4 task laws:

- correct hard-selection rate = 3/3 seeds;
- mean probability assigned to the correct family > 0.90;
- hard-selected training accuracy > 0.98;
- hard-selected near-OOD pair accuracy > 0.95;
- hard-selected far-OOD pair accuracy > 0.95.

No threshold may change after the first CI result.

## Interpretation boundary

A PASS would establish finite-library structural hypothesis selection from task
data. It would still not constitute unrestricted discovery of a new algebra,
LLM reasoning, Sophontic replication, a 60x efficiency result, or evidence for
data-center obsolescence.
