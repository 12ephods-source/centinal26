# dS2 local-net / modular convergence contract

This candidate advances the gate explicitly left open by merged PR #393 without promoting a finite correlation calculation into a von Neumann-algebra convergence theorem.

## What is implemented

The numerical subgate freezes three nested spatial regions `A subset B subset C`, four compactly supported phase-space smearings, a modular-parameter grid, two continuum mode cutoffs, and five lattice sizes.

For the free massless Dirichlet scalar at `beta=2*pi`, the code computes thermal Weyl two-point functions

`omega_beta(W(xi) sigma_s(W(eta)))`

using the exact mode-by-mode thermal covariance and the KMS identity

`sigma_s = alpha_{-beta s}`.

The continuum result is refined from 512 to 1024 sine modes. The finite-difference harmonic chain is refined over `N=16,32,64,128,256`. The diagnostic compares the complex modular-flow Weyl two-point functions over every frozen smearing pair and modular parameter, checks state-invariance inside each regulator, and verifies that the compact supports have the declared nested-region memberships.

## Why this is stronger than PR #393

PR #393 established two separate regulator limits for selected bounded Weyl/covariance observables. This candidate adds:

- phase-space smearings with both field and momentum components;
- complex Weyl product phases, not only one-point characteristics;
- explicit modular/KMS evolution on the frozen observable family;
- nested local-region bookkeeping;
- a separate written contract for what a future operator-topology promotion would actually require.

## PASS meaning

A green numerical result is only:

`PASS_DENSE_LOCAL_WEYL_MODULAR_CORRELATOR_SUBGATE`

It establishes controlled convergence on the frozen finite dense-test-family proxy. It is a necessary numerical subgate, not the full local-net/operator-topology gate.

## Explicitly still open

This candidate does **not** establish:

- strong or weak convergence of the full local von Neumann net;
- strong-resolvent convergence of modular generators;
- convergence of Tomita operators on a common core;
- a common-GNS or standard-subspace approximation theorem;
- Type-III1 classification from finite numerics;
- interacting de Sitter convergence;
- Type-II gravity, Hollands-Wald energy, or Einstein dynamics.

The next gate is therefore frozen as:

`COMMON_GNS_OR_STANDARD_SUBSPACE_OPERATOR_TOPOLOGY_CONVERGENCE`.

This ceiling is consistent with the continuum-target/source separation already enforced by PR #389 and the bounded bridge ceiling in PR #393.
