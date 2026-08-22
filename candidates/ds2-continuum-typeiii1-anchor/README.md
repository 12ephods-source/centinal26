# dS2 continuum Type-III1 source anchor

This gate separates two questions that had previously been entangled:

1. **Does a mathematically defined continuum Type-III1 de Sitter local algebra exist for the free dS2 scalar model?**
2. **Has the repository's finite matrix regulator been shown to converge to that algebra?**

The answer to (1) is source-anchored **yes**. The answer to (2) remains **no**.

## Continuum target

Barata, Jaekel, and Mund, *The P(phi)_2 Model on de Sitter Space*, Memoirs AMS 281 (2023), Proposition 8.2.3(iii), state that for every open interval `I` on the time-zero circle, the canonical free-field local observable algebra `R(I)` is *-isomorphic to the unique hyperfinite Type-III1 factor.

Jaekel and Mund's canonical de Sitter construction also records the Lorentz-invariant geodesic-KMS vacuum property used as the equilibrium/modular anchor.

This is exactly the continuum class needed by the free dS2 line already represented by the finite geometry-bearing surrogate reconciled in PR #327.

## What this changes

Previous status:

`UNRESOLVED_MISSING_INDUCTIVE_OR_INFINITE_PRODUCT_LIMIT_DATA`

After PR #387, the repository has a theorem-calibrated infinite-product Type-III construction control, but that control is deliberately Type `III_lambda`, not the physical dS2 target.

This source anchor now fixes the physical continuum target independently as:

`canonical free dS2 local net -> hyperfinite Type III_1`.

The finite-to-continuum approximation relation remains a separate gate.

## Structural bridge requirement

The existing finite numerical regulator uses both a finite oscillator occupation cutoff and a finite number of field modes/sites. These limits must not be conflated.

A controlled bridge therefore needs two axes:

1. **local-dimension limit:** truncated oscillator matrices must converge, for bounded Weyl/displacement observables and selected states, to the corresponding untruncated oscillator representation;
2. **field-mode/spatial limit:** the resulting finite-mode CCR/Weyl observables and correlations must converge for local smearings toward the continuum free-field net.

There is no exact finite-dimensional representation of the canonical commutation relations, so an exact *-embedding from the finite matrix oscillator cutoff into the continuum CCR algebra is not an admissible requirement. The bridge must instead specify bounded-observable/state convergence and then, separately, a continuum net/topology criterion.

## Promotion ceiling

`PASS_DS2_CONTINUUM_TYPE_III1_SOURCE_ANCHOR`

This status identifies the continuum target from primary sources. It does not promote any finite matrix algebra to Type III1, does not prove local-net convergence, and does not imply Type-II gravitational crossed products, canonical energy, Einstein dynamics, or observer gluing.
