# Geometric Symbolic Reasoning v3 — Continuous Negative-Control Gate

This is a separately versioned successor to closed, unmerged PR #142.

PR #142 remains frozen as a v2 gate FAIL. v3 does not edit its data, thresholds,
results, or interpretation.

## Why v3 exists

v2 produced a strong positive effect for the causally coupled geometry but failed
its preregistered negative-control criterion because the bounded pair-accuracy
baseline was already at the metric floor:

- baseline pair32 ≈ 0.003
- wrong-geometry pair32 = 0.000

The required condition `wrong < baseline - 0.05` was therefore impossible to
satisfy even though wrong geometry was at the floor. v2 correctly remained FAIL.

v3 addresses only this measurement defect by preregistering a continuous,
unbounded-above negative-control metric: held-out 64-step logistic loss. It also
uses fresh seeds 10, 11, and 12 and a longer OOD horizon of 64 steps.

## Frozen design

Architecture, optimizer, training distribution, and geometry objective are the
same mechanism class as v2.

Conditions:
- `baseline`
- `correct_geo`
- `wrong_geo`

Training chains: lengths 1–4.
Held-out evaluation: lengths 32 and 64.
Fresh seeds: 10, 11, 12.

## Preregistered v3 PASS gate

PASS requires all of:

1. correct OOD64 accuracy > baseline + 0.10;
2. correct pair64 accuracy > baseline + 0.10;
3. correct invariant64 accuracy >= baseline - 0.05;
4. correct OOD64 logistic loss < 0.80 × baseline loss;
5. wrong OOD64 logistic loss > 1.05 × baseline loss;
6. correct pair64 continuous margin > baseline + 0.10.

No threshold may be changed after the first v3 CI result. If this gate fails,
v3 is preserved as FAIL and any successor becomes v4.

## Scope boundary

Even a PASS supports only the toy claim that a task-aligned, causally coupled
latent representation of the correct Z2 operator algebra improves long-horizon
symbolic composition under this controlled setup. It does not establish
Sophontic's proprietary method, transformer-scale generalization, a 60x compute
advantage, or data-center obsolescence.
