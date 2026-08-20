# Geometric Symbolic Reasoning v6 — Structurally Exact Algebra Reference

This is a mechanism-changing successor to closed, unmerged PR #150.

PR #150 showed that exact SO(4) operators plus a **soft** correct-C4 relation
penalty did not outperform matched controls. v6 therefore removes relation-loss
optimization entirely and enforces candidate algebras structurally.

## Question

If the correct C4 algebra is built exactly into the latent transition family,
does it provide durable compositional generalization that identically
parameterized wrong/generic structures do not?

This is an inductive-bias reference test. A PASS would **not** mean that a neural
network learned or discovered C4 from data.

## Task

Four symbols have the task law:

`target = sum(symbols) mod 4`.

Training lengths: 1–4.
Near OOD: 11/12/13.
Far OOD: 61/62/63.
Fresh seeds: 40/41/42.

A canonical/perturbed pair increments one input symbol by one modulo four; the
correct output class must also increment by one.

## Conditions

All conditions use the same model shell, learnable start state, four-class head,
and dormant parameter slots so declared capacity is not reduced in the favored
arm.

1. `exact_c4`: exact C4 regular-representation operators, conjugated by a learned
   SO(4) latent basis.
2. `wrong_v4`: exact Klein-four regular-representation operators with the same
   learned-basis parameterization.
3. `generic_fixed`: four fixed orthogonal permutation operators that do not form
   the target C4 law, in the same learned basis.
4. `independent_so4`: four unrelated learned SO(4) transition operators; this is
   a more flexible baseline.

There is no relation penalty in v6. C4/V4 structure is exact by construction.

## Frozen v6 gate

PASS requires all of:

- exact C4 training accuracy > 0.98;
- exact C4 near pair accuracy > 0.95;
- exact C4 far pair accuracy > 0.95;
- exact C4 near pair accuracy > each control by 0.10;
- exact C4 far pair accuracy > each control by 0.20.

No threshold may be changed after the first CI result.

## Interpretation boundary

A PASS establishes sufficiency/specificity of an explicitly supplied correct
algebraic inductive bias on this toy task. It does not establish latent-algebra
discovery, Sophontic's method, transformer-scale generalization, 60x compute
efficiency, or data-center obsolescence.
