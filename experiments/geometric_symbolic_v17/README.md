# Geometric Symbolic v17 — matched dose replication

Successor to PR #168 v16. The prior three-seed sequence bracketed 6.25% FAIL versus 6.875% PASS, but those doses used different small seed sets. v17 is a confirmatory matched-seed replication rather than another midpoint search.

## Frozen design

Run the exact v11 model/data/training/evaluation implementation at both 6.25% and 6.875% singleton-anchor frequency using the same 12 fresh seeds, 150-161. At each dose, retain exact-C4, deliberately wrong-V4, and GRU arms with identical 700-step budget, noisy 12-D surfaces, canonical/perturbed pairs, output-level counterfactual loss, near OOD lengths 11/12/13, and far OOD lengths 61/62/63.

A seed is an exact-C4 reliability success only if singleton accuracy >0.98, token grounding >0.98, paired training >0.95, near-pair >0.95, and far-pair >0.90.

## Frozen PASS gate

All required before first CI result:
- the 6.875% dose has more reliability-success seeds than 6.25%;
- a one-sided exact McNemar test on matched seed successes gives p < 0.05;
- 6.875% succeeds on at least 9/12 fresh seeds;
- mean 6.875% exact-C4 far-pair accuracy exceeds wrong-V4 and GRU by >0.20;
- exact-C4 parameter count <= GRU.

No post-result threshold edits are allowed.

## Scope

PASS would support only a dose-dependent reliability difference in this synthetic sparse-anchor mechanism over this fixed 6.25%-6.875% comparison. FAIL preserves the earlier small-seed observations but rejects this stronger matched replication claim. Neither outcome establishes a universal critical anchor probability, Sophontic replication, natural-language reasoning, 60x/1000x efficiency, or data-center obsolescence.
