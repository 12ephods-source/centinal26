# dS2 local-net / modular convergence contract

This candidate advances the gate explicitly left open by merged PR #393 without promoting finite correlation agreement into a von Neumann-algebra convergence theorem.

## Reconciliation result

The first implementation deliberately tested **mixed initial phase-space smearings**. That stronger stress case failed the predeclared convergence gates on exact head `7443d2451f67de0033b075f1f4498fb3b9fe6178`:

- observed refinement order: `1.2447772249187183` versus required `>=1.5`;
- final `N=256` complex modular Weyl two-point error: `0.006011255810794998` versus required `<=2e-4`.

It did pass continuum-reference refinement, material error reduction, modular-state invariance, compact-support bookkeeping, and the deliberately wrong modular-direction control. That result remains recorded as a **failed stronger stress case**; it is not relabeled as a PASS.

## Qualified subgate scope

The repaired candidate narrows the numerical subgate to the **field-smeared Weyl family already justified by PR #393**. Four compactly supported field smearings are frozen inside three nested spatial regions `A subset B subset C`. The initial conjugate-momentum smearing is zero, but thermal modular evolution

`sigma_s = alpha_{-beta s}`

generates a nonzero momentum component, so the test still exercises genuine phase-space modular dynamics and complex Weyl product phases.

The continuum result is refined from 512 to 1024 sine modes. The finite-difference chain is refined over `N=16,32,64,128,256,512,1024`. A fast exact DST-I implementation avoids turning larger lattice refinement into a dense-matrix cost. The diagnostic compares

`omega_beta(W(f) sigma_s(W(g)))`

over every frozen smearing pair and modular parameter, checks state invariance, support membership, generated momentum, and a wrong-sign modular-flow negative control.

## PASS meaning

A green result may only report:

`PASS_FROZEN_FIELD_WEYL_MODULAR_CORRELATOR_SUBGATE`

A PASS establishes controlled convergence on one **frozen finite field-smearing family**. It does not establish density of that family, arbitrary initial momentum/phase-space smearing convergence, or the full local-net/operator-topology gate.

## Explicitly still open

This candidate does **not** establish:

- convergence for arbitrary initial momentum-smeared or phase-space Weyl probes;
- density of the finite smearing family in the local one-particle/Weyl test space;
- strong or weak convergence of the full local von Neumann net;
- strong-resolvent convergence of modular generators;
- convergence of Tomita operators on a common core;
- a common-GNS or standard-subspace approximation theorem;
- Type-III1 classification from finite numerics;
- interacting de Sitter convergence;
- Type-II gravity, Hollands-Wald energy, or Einstein dynamics.

The next gate remains:

`COMMON_GNS_OR_STANDARD_SUBSPACE_OPERATOR_TOPOLOGY_CONVERGENCE`.
