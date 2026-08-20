# Geometric Symbolic v11 — singleton-anchor grounding

Successor to PR #156 v10. v10 showed a mixed result: one exact-C4 seed reached perfect grounding/generalization while two seeds failed to identify the latent surface mapping. v11 does not retune v10 and does not change its thresholds or evidence.

## Frozen intervention

Every model receives the same training stream, parameter budget class, optimizer, 700 steps, noisy 12-D surface observations, canonical/perturbed sequence pairs, final sequence labels, and output-level counterfactual loss used in v10.

The only mechanism change is preregistered before CI: 10% of training batches use length-one sequences. These remain ordinary sequence-label examples; there is no separate token/encoder supervision objective. The remaining 90% follow the paired length 2→5 curriculum.

Fresh seeds: 90/91/92. Near OOD: 11/12/13. Far OOD: 61/62/63.

Controls:
- exact C4 structured model, 276 parameters;
- identically parameterized wrong V4 structured model;
- slightly larger unconstrained GRU baseline, 309 parameters.

## Frozen PASS gate

All required:
- exact-C4 singleton accuracy > 0.98;
- exact-C4 token grounding > 0.98;
- exact-C4 paired train > 0.95;
- exact-C4 near pair > 0.95;
- exact-C4 far pair > 0.90;
- exact-C4 far pair beats wrong V4 by > 0.20;
- exact-C4 far pair beats GRU by > 0.20;
- structured parameter count <= GRU.

No threshold changes after first CI.

## Scope

A PASS would establish only that sparse sequence-level singleton anchors stabilize this synthetic neural-to-exact-algebra grounding setup. It would not establish unrestricted algebra discovery, natural-language or transformer reasoning, Sophontic replication, training-FLOP efficiency, 60× scaling, 1000× efficiency, or data-center obsolescence.
