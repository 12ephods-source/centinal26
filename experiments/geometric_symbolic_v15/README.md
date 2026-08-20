# Geometric Symbolic v15 — boundary singleton-anchor dose test

Successor to PR #166 v14. v14 passed at a 7.5% singleton-anchor rate; v13 failed the unchanged frozen checker at 5%. v15 preserves both results unchanged and tests the preregistered midpoint, 6.25%.

## Frozen intervention

Reuse the exact v11 model, noisy 12-D surfaces, canonical/perturbed pairs, output-level counterfactual loss, optimizer, 700-step budget, evaluation lengths, exact-C4 arm, wrong-V4 control, and GRU baseline. Change only singleton-anchor rate to 6.25% and use fresh seeds 130/131/132. All model families receive the same anchor schedule.

## Frozen PASS gate

Unchanged from v11-v14: exact-C4 singleton and latent grounding >0.98; paired train and near-pair >0.95; far-pair >0.90; far-pair advantage >0.20 over wrong-V4 and GRU; structured parameter count <= GRU.

No threshold changes after first CI.

## Scope

PASS would establish only that this synthetic mechanism is reliable at the preregistered 6.25% anchor dose on fresh seeds. FAIL would show that 6.25% is insufficient under this setup. This brackets an anchor-dose reliability transition; it is not a Sophontic replication, natural-language reasoning result, training-FLOP efficiency measurement, 60x/1000x scaling claim, or data-center-obsolescence claim.
