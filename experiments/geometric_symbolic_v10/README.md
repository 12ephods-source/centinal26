# Geometric Symbolic Reasoning v10 — Paired Counterfactual Neural Grounding

This is a separately versioned successor to closed, unmerged PR #154.

v9 showed that a neural surface encoder did not ground noisy observations into
latent C4 elements under isolated sequence-level supervision. v10 tests the
paired perturbation hypothesis directly.

## Training signal

Every training example is a canonical/perturbed pair. One load-bearing latent
element is incremented by one modulo four in the perturbed sequence, so the
correct final C4 class must also increment by one.

The model receives:
- canonical noisy surface sequence + final sequence label;
- perturbed noisy surface sequence + final sequence label.

It never receives a token-level latent-element label.

All three model families receive the same pair curriculum and the same
output-level counterfactual consistency loss, which requires the perturbed
output distribution to be the canonical output distribution shifted by +1.

Training curriculum grows from length 2 to lengths 2–5 over 700 steps.
Near OOD: 11/12/13.
Far OOD: 61/62/63.
Fresh seeds: 80/81/82.
Surface noise sigma: 0.12.

## Models

- `exact_c4`: 276-parameter neural surface encoder + exact C4 latent composition.
- `wrong_v4`: identical 276-parameter encoder with wrong exact V4 composition.
- `gru`: 309-parameter unconstrained recurrent baseline.

## Frozen v10 gate

PASS requires all of:

- exact-C4 paired training accuracy > 0.95;
- independently measured token-grounding accuracy > 0.98;
- near-OOD pair accuracy > 0.95;
- far-OOD pair accuracy > 0.90;
- exact-C4 far pair > wrong-V4 far pair + 0.20;
- exact-C4 far pair > GRU far pair + 0.20;
- exact-C4 parameter count <= GRU parameter count.

No threshold may change after first CI.

## Interpretation boundary

A PASS would support the specific synthetic claim that canonical/perturbed
sequence-level supervision can train a compact neural surface encoder to ground
observations into an exact latent algebra, producing long-horizon gains at
comparable parameter count. It would still not establish natural-language/LLM
reasoning, training-FLOP efficiency, Sophontic's proprietary method, a 60x
claim, or data-center obsolescence.
