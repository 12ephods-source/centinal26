# Geometric Symbolic Reasoning v4 — Anti-Aliasing Negative Control

This is a separately versioned successor to closed, unmerged PR #147.

PR #147 remains frozen as v3 FAIL. v4 does not alter any earlier result or threshold.

## Design flaw isolated from v2/v3

The earlier wrong-geometry arm swapped positive and negative edge semantics.
For a parity task at fixed even length L:

`(-1)^N_positive = (-1)^(L-N_negative) = (-1)^N_negative`

because `(-1)^L = +1` when L is even.

Therefore the swapped rule is algebraically equivalent to the correct parity label on the
32- and 64-step evaluations. That made the negative control aliased by task symmetry.

## v4 correction

v4 changes only the successor experiment:
- fresh seeds: 20, 21, 22;
- mixed odd/even near-OOD lengths: 15, 16, 17;
- mixed odd/even far diagnostic lengths: 31, 32, 33;
- genuinely false active control: both edge symbols are constrained to reflect the task coordinate.

The model architecture, optimizer, short-chain training distribution, causal 2-D task subspace,
and geometric-loss weight remain in the same mechanism class as v2/v3.

## Frozen v4 gate

PASS requires all of:
1. correct near-OOD accuracy > baseline + 0.10;
2. correct near-OOD pair accuracy > baseline + 0.10;
3. correct near-OOD distractor invariance >= baseline - 0.03;
4. wrong near-OOD accuracy < baseline - 0.05;
5. wrong near-OOD pair accuracy < baseline - 0.05.

The 31/32/33 results are diagnostic only in v4. If soft learned operators still collapse there,
that becomes evidence for a separate exact-group-manifold successor rather than a reason to edit v4.

No gate threshold may be changed after the first CI result.

## Scope boundary

Even a PASS would support only this controlled toy Z2 mechanism. It would not establish
Sophontic's proprietary method, transformer-scale generalization, 60x efficiency, or
data-center obsolescence.
