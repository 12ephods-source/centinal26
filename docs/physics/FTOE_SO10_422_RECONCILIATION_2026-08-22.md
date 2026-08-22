# FToE SO(10) / G422 reconciliation — 2026-08-22

This document preserves the validated scientific state of stale PR #105 on current `main` without importing its 176-commit stacked history.

## Source identity

- PR: #105, `Add falsification-gated FToE SO10 422 closure harness`
- exact source head: `e6ea779bca4e2703dcc157c1a76e13199d4ae912`
- repository qualification on that exact head: CI PASS; validate PASS; automation-gates PASS; federation-gates PASS; Mature Product Qualification PASS; dedicated `FToE SO10 422 Gate` PASS; protected-I and scalar-action dedicated gates PASS.

These PASS states establish deterministic software/numerical reproduction of the frozen calculations. They do **not** establish scientific closure of FToE.

## Preserved gauge-only result

For the frozen informational-doublet threshold near 13.4916 TeV, the source branch records

- `M_I = 7.0374912e9 GeV`,
- `M_U = 2.0499099e16 GeV`,
- `alpha_U = 0.03206733`,
- maximum inverse-coupling spread about `2.04e-11`.

The corresponding hierarchy scan prefers `n=9` in the source convention, i.e. a schematic dimension-13 contribution with `c_9 C_eff ~= 2.04`. This is numerical compatibility, not a derivation of the required SO(10) singlet operator.

## Preserved falsifications / exclusions

The source result keeps three branches fail-closed:

1. ordinary embedded light informational doublet: **FAIL**;
2. ordinary finite-dimensional unitary linear internal-symmetry protection of the norm portal: **FAIL**;
3. single-spurion GUT-scale pNGB protection under the frozen diagnostic estimate: **FAIL**.

The key structural observation is that scalar norms are separately invariant under ordinary unitary linear internal symmetries, so the norm portal `(I^dagger I)(Phi^dagger Phi)` is not forbidden by such a symmetry. At the recorded `M_U`, the source naturalness estimate requires a generic unprotected portal coupling of order `2.17e-25` or smaller.

The source also preserves the `45+126+10_C` invariant basis only as a restricted core sub-potential; it is not the full scalar action once `210_H` and the protected informational sector are included.

## Mandatory unresolved gates

Scientific status remains **REVIEW_FAIL_CLOSED** until all applicable missing work is closed without post-result retuning:

- explicit nonlinear/collective/sequestered/exact protection mechanism with demonstrated radiative stability;
- complete renormalizable `210_H + 45_H + 126_H + 10_C,H + protected-I` scalar action;
- vacuum, Hessian, heavy spectrum, and light-Higgs perturbativity from that frozen action;
- threshold corrections from the frozen spectrum without tuning masses after the result;
- explicit preferred-dimension SO(10) singlet operator and computed `C_eff`;
- exhaustive lower-dimensional invariant exclusion/suppression;
- independent derivation of `mu_I` before `mu_I -> Lambda_X -> beta` propagation;
- `p -> e+ pi0` from the same spectrum;
- manuscript-level reproducibility from identical frozen inputs and provenance.

## Relationship to current main

Current main already contains narrower successor/reconciliation results: the bounded L1 UV-closure module from former PR #109, the `10_C,H` self-sector reconciliation, and the later UV-matching bifurcation result from PR #308. This reconciliation preserves the broader gauge/naturalness/protection state of #105 as provenance while avoiding a bulk merge of stale ancestry.

**Promotion rule:** software or CI success is not scientific confirmation. The scientific state remains REVIEW until the missing protection, full-action, spectrum, threshold, operator, proton-decay, and reproducibility gates are independently satisfied.
