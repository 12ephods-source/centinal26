# Geometric Symbolic Reasoning v2 — Causally Coupled Z2 Gate

This is a separately versioned successor to closed, unmerged PR #121.

PR #121 is frozen as a negative result. This experiment does not edit its model, thresholds, data, interpretation, or evidence.

## Hypothesis

The v1 auxiliary scalar probe could be ignored by the actual prediction head. v2 puts the structured latent subspace directly on the causal prediction path:

`hidden state -> 2-D task subspace -> first coordinate -> answer logit`

For the correct geometry:
- positive edge: identity;
- negative edge: reflection of the task coordinate;
- distractor changes: invariant in the task subspace.

The wrong-geometry arm swaps the positive/negative operator semantics.

## Matched conditions

- `baseline`
- `correct_geo`
- `wrong_geo`

Architecture, optimizer, data distribution, training steps, seeds, and evaluation procedures are otherwise held fixed.

## Split

- training chain lengths: 1–4
- OOD chain lengths: 8, 16, 32
- primary counterfactual metric: exact canonical/perturbed pair accuracy at 32

## Frozen v2 checker

PASS requires:
- correct pair32 > baseline pair32 + 0.10
- correct OOD32 > baseline OOD32 + 0.08
- correct invariant32 >= baseline invariant32 - 0.03
- wrong pair32 < baseline pair32 - 0.05

If floor effects make the final criterion inappropriate, this v2 gate still fails. Any replacement criterion belongs in separately versioned v3 and must not be retrofitted into v2.

## Scope

Even a PASS would support only this toy symbolic mechanism. It would not establish Sophontic's proprietary method, 60x efficiency, transformer-scale generalization, or data-center obsolescence.
