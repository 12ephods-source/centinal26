# Geometric Symbolic Reasoning v5 — Exact Group-Specificity Gate

This is a mechanism-changing successor to closed, unmerged PR #148.

PR #148 remains frozen as FAIL/REVIEW. It showed that a deliberately false soft
geometric regularizer could outperform the nominally correct one, so soft-penalty
gains could not be attributed specifically to correct latent algebra.

## v5 question

When every condition already uses exact norm-preserving operator composition,
does imposing the **correct algebraic relation** improve generalization beyond:

- no structural relation penalty;
- a matched generic operator-separation penalty; and
- an equally structured but incorrect group law?

## Task

Four symbols compose under the cyclic group `C4`:

`target = sum(symbols) mod 4`.

Training chain lengths are 1–4. OOD evaluation uses mixed lengths 11/12/13 and
31/32/33. A canonical/perturbed pair increments one symbol by one modulo four,
so the correct final class must also increment by one.

Fresh seeds: 30, 31, 32.

## Shared architecture

Every condition uses the same four learned `SO(4)` transition operators,
constructed exactly as matrix exponentials of skew-symmetric generators. Thus
operator norm preservation is not unique to the favored condition.

Conditions:

1. `baseline` — exact SO(4) operators, task loss only.
2. `generic` — same operators plus a pairwise operator-separation penalty.
3. `correct_c4` — same operators plus the correct C4 multiplication relation.
4. `wrong_v4` — same operators plus the equally structured but incorrect
   Klein-four/XOR multiplication relation.

The C4 and V4 penalties have identical form and number of relation terms; only
the multiplication table differs.

## Frozen v5 gate

PASS requires all of:

- correct C4 pair accuracy > baseline by 0.10 at near OOD;
- correct C4 pair accuracy > generic by 0.10 at near OOD;
- correct C4 pair accuracy > baseline by 0.10 at far OOD;
- correct C4 pair accuracy > generic by 0.10 at far OOD;
- correct C4 pair accuracy > wrong V4 by 0.10 at near OOD;
- correct C4 pair accuracy > wrong V4 by 0.10 at far OOD;
- the learned correct-C4 arm has C4 relation residual < 0.75 × the wrong-V4 arm.

No threshold may be changed after the first v5 CI result. Failure is preserved;
any successor becomes v6.

## Interpretation boundary

A PASS would establish only that correct relation structure adds value over
matched controls in this exact-operator toy task. It would not reproduce
Sophontic, establish transformer-scale reasoning gains, verify a 60x efficiency
claim, or imply that AI data centers become obsolete.
