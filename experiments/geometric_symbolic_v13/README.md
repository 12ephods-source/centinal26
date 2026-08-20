# Geometric Symbolic v13 — midpoint singleton-anchor dose test

Successor to PR #161 v12. v11 passed at a 10% singleton-anchor rate; v12 failed the unchanged frozen checker at 2%, with one of three exact-C4 seeds grounding successfully. v13 preserves both results unchanged and tests a preregistered midpoint dose.

## Frozen intervention

Reuse the exact v11 model, noisy 12-D surfaces, canonical/perturbed pairs, output-level counterfactual loss, optimizer, 700-step budget, evaluation lengths, exact-C4 arm, wrong-V4 control, and GRU baseline. Change only singleton-anchor rate to 5% and use fresh seeds 110/111/112. All model families receive the same 5% anchor schedule.

## Frozen PASS gate

Unchanged from v11/v12: exact-C4 singleton and latent grounding >0.98; paired train and near-pair >0.95; far-pair >0.90; far-pair advantage >0.20 over wrong-V4 and GRU; structured parameter count <= GRU.

No threshold changes after first CI.

## Scope

PASS would establish only that this synthetic mechanism is reliable at the preregistered 5% anchor dose on fresh seeds. FAIL would show that 5% is also insufficient under this setup. This brackets an anchor-dose transition; it is not a Sophontic replication, natural-language reasoning result, training-FLOP efficiency measurement, 60x/1000x scaling claim, or data-center-obsolescence claim.
