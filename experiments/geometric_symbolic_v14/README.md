# Geometric Symbolic v14 — upper-midpoint singleton-anchor dose test

Successor to PR #165 v13. v11 passed at a 10% singleton-anchor rate; v13 failed the unchanged frozen checker at 5%. v14 preserves both results unchanged and tests the preregistered upper midpoint, 7.5%.

## Frozen intervention

Reuse the exact v11 model, noisy 12-D surfaces, canonical/perturbed pairs, output-level counterfactual loss, optimizer, 700-step budget, evaluation lengths, exact-C4 arm, wrong-V4 control, and GRU baseline. Change only singleton-anchor rate to 7.5% and use fresh seeds 120/121/122. All model families receive the same anchor schedule.

## Frozen PASS gate

Unchanged from v11-v13: exact-C4 singleton and latent grounding >0.98; paired train and near-pair >0.95; far-pair >0.90; far-pair advantage >0.20 over wrong-V4 and GRU; structured parameter count <= GRU.

No threshold changes after first CI.

## Scope

PASS would establish only that this synthetic mechanism is reliable at the preregistered 7.5% anchor dose on fresh seeds. FAIL would show that 7.5% is also insufficient under this setup. This brackets an anchor-dose reliability transition; it is not a Sophontic replication, natural-language reasoning result, training-FLOP efficiency measurement, 60x/1000x scaling claim, or data-center-obsolescence claim.
