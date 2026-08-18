# Geometric Symbolic Reasoning — Canonical/Perturbed Pair Gate

Parent evidence:
- PR #118 head: `b68453c7bdff2890aff292506a5c5447a0806436`
- Parent `geometric-reasoning` CI: PASS
- Parent evidence artifact digest: `sha256:68f33695c1c9c3009aed251ea0d207f1efdd5d69eb0acb45d51e90d4fc2b8f7d`

## Question
Does an explicitly correct latent algebra improve symbolic compositional generalization and counterfactual pair consistency beyond ordinary task training?

## Task
A chain consists of signed implication edges:
- `+1`: preserve logical polarity.
- `-1`: negate logical polarity.

The correct chain result is the product of edge signs, i.e. the Z2 composition law. Each step also includes an irrelevant distractor bit.

### Canonical / perturbed pair
For each canonical chain, exactly one load-bearing edge is flipped. Therefore the correct answer must flip.

### Invariant pair
Only a distractor bit is flipped. Therefore the correct answer must not change.

## Conditions
All conditions use the same architecture and training-step count and compute both candidate geometric losses.

1. `baseline`: task loss only.
2. `correct_geo`: task loss + the correct latent rule: positive edges preserve latent parity, negative edges reflect latent parity, and two negative edges compose back to identity.
3. `wrong_geo`: same machinery but deliberately incorrect semantics: positive edges flip parity and negative edges preserve parity.

## Split
- Train chain lengths: 1–4.
- OOD evaluation: lengths 8 and 16.
- Primary metric: pair-level exact accuracy at length 16.

## Preregistered gate
PASS requires:
- `correct_geo pair16 > baseline pair16 + 0.10`;
- `correct_geo ood16 > baseline ood16 + 0.05`;
- correct-geometry distractor invariance is not worse than baseline by more than 0.03;
- `wrong_geo pair16 < baseline pair16 - 0.05`.

A PASS supports only this toy symbolic mechanism. It does not establish Sophontic's implementation, 60× scaling, or data-center obsolescence.

## First full diagnostic (one seed; preserved, not promoted)

The first 500-step full diagnostic was run only after the gate logic above had already been written locally.

| Condition | OOD-16 accuracy | Pair-16 accuracy | Invariant-16 accuracy |
|---|---:|---:|---:|
| baseline | 0.9727 | 0.9475 | 0.9740 |
| correct_geo | 0.9004 | 0.7961 | 0.8939 |
| wrong_geo | 0.7990 | 0.6178 | 0.8043 |

Status: **FAIL/REVIEW for the reconstructed symbolic geometry objective.**

The correct-geometry regularizer harmed performance relative to baseline on this task. The wrong-geometry control harmed it more strongly. No post-result retuning is permitted on this branch. GitHub CI runs the unchanged three-condition experiment across three seeds; if the original gate fails, preserve the failure and branch to a separately versioned successor hypothesis.
