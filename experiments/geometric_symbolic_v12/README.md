# Geometric Symbolic v12 — low-dose singleton-anchor stress test

Successor to PR #158 v11. v11 exact-head CI established a narrow synthetic PASS with a 10% singleton-anchor rate. v12 does not alter v11 evidence or thresholds.

## Frozen intervention

Reuse the exact v11 model, noisy 12-D surfaces, canonical/perturbed pairs, output-level counterfactual loss, optimizer, 700-step budget, evaluation lengths, exact-C4 arm, wrong-V4 control, and GRU baseline. Change only the singleton-anchor rate from 10% to 2% and use fresh seeds 100/101/102.

This is a dose-reduction stress test, not a compute-efficiency claim. All model families receive the same 2% anchor schedule.

## Frozen PASS gate

Use the unchanged v11 scientific thresholds: exact-C4 singleton and latent grounding >0.98; paired train and near-pair >0.95; far-pair >0.90; far-pair advantage >0.20 over wrong-V4 and GRU; structured parameter count <= GRU.

No threshold changes after first CI.

## Scope

PASS would show only that the synthetic sparse-anchor mechanism remains reliable at a five-fold lower anchor frequency on fresh seeds. FAIL would establish that the v11 result is not robust to this anchor-dose reduction. Neither outcome establishes Sophontic replication, natural-language reasoning, training-FLOP efficiency, 60x/1000x scaling, or data-center obsolescence.
