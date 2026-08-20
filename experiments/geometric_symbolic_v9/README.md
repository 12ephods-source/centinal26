# Geometric Symbolic Reasoning v9 — Neural Surface Grounding

This is the bridge after PR #153's hidden-mapping finite-library PASS.

v8 recovered algebra family and hidden discrete symbol semantics by selecting
among 48 explicit hypotheses. v9 stops enumerating token mappings and replaces
symbols with noisy continuous observations.

## Question

Can a small neural surface encoder infer latent operations from sequence-level
answers and feed them into an exact algebraic core, yielding long-horizon
compositional generalization that a similarly sized unconstrained recurrent
network and a wrong exact algebra do not?

## Data

Each latent C4 element has a seed-specific 12-dimensional prototype. Every
observed token is the prototype plus Gaussian noise (`sigma=0.12`).

Training supervision is only the final composition class. The model never
receives per-token latent-element labels.

Training chain lengths: 2–5.
Near OOD: 11/12/13.
Far OOD: 61/62/63.
Fresh seeds: 70/71/72.

## Models

### `exact_c4`
A `12 -> 16 -> 4` neural encoder predicts a latent categorical distribution for
each noisy surface observation. Those distributions are composed using the
**exact C4 convolution law**. At evaluation, the encoder is hardened with
`argmax` per token before exact composition.

### `wrong_v4`
Identical neural encoder, parameter count, optimization, and data, but the exact
latent core composes with the wrong V4/XOR law.

### `gru`
A parameter-matched/slightly larger unconstrained GRU consumes the same surface
features and predicts the final class directly.

The experiment records exact parameter counts. The favored structured model is
required not to exceed the GRU parameter count.

## Frozen v9 gate

PASS requires all of:

- exact-C4 training accuracy > 0.95;
- independently measured latent token-grounding accuracy > 0.98;
- near-OOD counterfactual pair accuracy > 0.95;
- far-OOD counterfactual pair accuracy > 0.90;
- exact-C4 far pair > wrong-V4 far pair + 0.20;
- exact-C4 far pair > GRU far pair + 0.20;
- exact-C4 parameter count <= GRU parameter count.

No threshold may change after first CI.

## Interpretation boundary

A PASS would establish a synthetic neural-grounding result: an exact latent
algebra can convert noisy learned surface representations into substantially
better long-horizon compositional generalization at comparable parameter count.
It would still not be natural-language reasoning, an LLM, a training-FLOP
comparison, Sophontic replication, or verification of a 60x efficiency claim.
