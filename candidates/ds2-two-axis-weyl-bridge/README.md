# dS2 two-axis bounded Weyl bridge

This gate implements the smallest honest numerical bridge between the finite matrix regulators and the source-anchored continuum free-field target.

## Why two axes are mandatory

The earlier bounded multi-mode stress family used a finite occupation dimension per oscillator and a finite number of modes. Those are different regulators.

A finite matrix oscillator cannot exactly satisfy the canonical commutation relation, so there is no exact CCR-preserving finite-dimensional *-embedding to the continuum Weyl algebra. Continuum promotion therefore requires at least:

1. a **local-dimension/occupation limit** to the ordinary untruncated oscillator representation for bounded observables;
2. a **field-mode/spatial limit** from finitely many oscillator modes to continuum smeared-field observables.

## Axis 1: local occupation dimension

For a thermal oscillator, the exact untruncated displacement expectation is

`<D(alpha)> = exp[-|alpha|^2 coth(beta*omega/2)/2]`.

The harness constructs the truncated ladder operator at `d = 2,4,8,12,16,24,32`, exponentiates the bounded finite generator, and compares the finite thermal expectation with the exact value over a frozen stress grid.

A required negative control is that `d=2` remains visibly inaccurate for the continuum bridge. This does **not** invalidate the earlier `d=2` finite-Type-I stress test; it only blocks using that cutoff as continuum evidence.

## Axis 2: spatial/mode refinement

For the massless free scalar on a unit Dirichlet interval at `beta=2*pi`, the harness chooses one smooth interior L2-normalized Gaussian smearing. It computes the continuum thermal covariance by the sine-mode expansion and independently computes the finite-difference harmonic-chain covariance at `N=16,32,64,128,256`.

It then checks:

- refinement of the continuum reference itself;
- monotone lattice error reduction;
- approximately second-order spatial convergence;
- convergence of the corresponding bounded Weyl characteristic `<exp(i t Phi(f))>` at three frozen amplitudes.

## PASS meaning

`PASS_TWO_AXIS_BOUNDED_WEYL_CORRELATOR_BRIDGE`

A PASS establishes only controlled convergence for the frozen bounded-observable/state diagnostics. It does not establish convergence of the full local net, any von Neumann-algebra topology, or the Type-III1 classification. The latter is independently source-anchored by PR #389, not numerically derived here.

The next gate must define and test a local-net topology/modular convergence contract strong enough to relate the continuum algebraic target to an increasing family of bounded local observables without claiming that a few correlation functions determine a von Neumann factor.
