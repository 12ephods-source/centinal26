# FToE L1–L4 Terminal Closure — 2026-08-17

Status: **CONVERSATION CLOSURE COMPLETE; FToE SCIENTIFIC PROGRAM REMAINS MULTI-BRANCH REVIEW**

This document freezes the terminal adjudication of Limitations L1–L4 for the present conversation. It deliberately does **not** open new theory branches to avoid an OPEN or FAIL verdict.

## Closure rule

Each limitation terminates as one of:

- **DERIVED** — the claimed result follows from a frozen model with independently fixed upstream inputs;
- **PARTIAL** — a substantive sub-result is derived but the limitation's full first-principles claim is not;
- **FAIL** — the tested formulation is internally inconsistent, excluded, or cannot supply the claimed result under its frozen assumptions;
- **OPEN / UNDERDETERMINED** — the necessary upstream model/input is not specified, so no unique derivation exists.

A newly discovered problem changes the verdict; it does not automatically authorize a replacement branch.

## L1 — first-principles derivation of mu_I

Claim tested: derive `mu_I ~= 9.54 TeV` from the SO(10) UV theory rather than selecting it from the target `beta ~= 1e-15`.

Verified engineering sub-results on PR #105:

- corrected `SO(10) -> G422 -> SM` gauge-only two-loop root with the informational doublet threshold at `m_I ~= 13.4916 TeV`;
- `M_I ~= 7.0374912e9 GeV`, `M_U ~= 2.0499099e16 GeV`, `alpha_U ~= 0.03206733`;
- preferred dimensional hierarchy power `n=9`, with schematic `c_9 C_eff ~= 2.04`;
- ordinary unprotected embedded-doublet branch fails technical naturalness: the generic norm portal requires suppression of order `(mu_I/M_U)^2 ~= 2.17e-25`;
- ordinary finite-dimensional unitary linear internal symmetries cannot forbid `(I^dagger I)(Phi^dagger Phi)` because each norm is separately invariant;
- a nontrivial exact constant additive shift is incompatible with the frozen electroweak-charged doublet and nonzero gauge coupling;
- the tested single-spurion GUT-scale pNGB estimate is far too large.

Missing for the claimed first-principles derivation:

- an explicit surviving nonlinear/collective/sequestered/lower-scale protection mechanism;
- the complete frozen `210_H + 45_H + 126_H + 10_C,H + protected-I` scalar action;
- vacuum/Hessian and heavy spectrum;
- an explicit SO(10)-singlet preferred-order mass operator and its Clebsch/contraction factor `C_eff`;
- exhaustive lower-dimensional operator suppression;
- independent generation of `mu_I` before propagating to `Lambda_X` and `beta`.

**Terminal verdict: L1 = OPEN / UNDERDETERMINED.**

Sub-branch verdicts preserved: ordinary embedded doublet = FAIL; ordinary linear-symmetry protection = FAIL; exact additive shift = FAIL; tested single-spurion GUT-scale pNGB branch = FAIL. A substantially different protection mechanism is future research, not completion of this limitation in the present conversation.

## L2 — dark-sector lambda_phi and v_phi

Claim tested: derive `lambda_phi = 0.121` and `v_phi = 146.9 GeV` from SO(10), then obtain the ~102 GeV dark scalar without fitting the relic abundance/mass.

Established arithmetic:

`m_phi = 2 sqrt(lambda_phi) v_phi` with the stated inputs gives approximately `102.2 GeV`.

However:

- the recalibrated FToE source explicitly labels `lambda_phi` and `v_phi` as stated/constrained rather than SO(10)-derived;
- the quartic RGE alone cannot determine the symmetry-breaking VEV; an independent running mass parameter/effective potential boundary condition is required;
- the minimal ~102 GeV Higgs-portal realization is incompatible with the source's relic-density/direct-detection requirements and was already revised to require unspecified suppression/additional structure;
- no frozen SO(10) dark-sector potential and boundary conditions have been supplied that generate both low-energy parameters independently.

**Terminal verdict: L2 = FAIL for the minimal portal realization; OPEN / UNDERDETERMINED for a replacement non-minimal SO(10) dark sector.**

The values `lambda_phi=0.121` and `v_phi=146.9 GeV` remain fitted/constrained inputs, not predictions.

## L3 — GUT-scale threshold corrections and exact unification

Claim tested: derive the heavy SO(10) spectrum and its threshold corrections, rather than adjust heavy masses to remove a residual coupling spread.

Established sub-results:

- the historical direct `SM + I` beta-function treatment was incorrect and the direct branch fails;
- the repaired intermediate `G422` gauge-only two-loop calculation is independently regression-tested and numerically closes the three couplings at approximately `M_U = 2.0499099e16 GeV`, `alpha_U = 0.03206733`;
- the active `G422` one-/two-loop coefficients are derived from a frozen representation registry, including provenance for the `b_(2L,4)=525/2` coefficient;
- a fail-closed threshold evaluator exists and refuses to optimize masses to force unification.

Still missing:

- the complete heavy spectrum derived from one frozen scalar potential;
- individual heavy masses and matching coefficients from that spectrum;
- threshold-corrected `M_I`, `M_U`, and `alpha_U` from those masses;
- proton decay computed from the same frozen spectrum.

**Terminal verdict: L3 = PARTIAL. Gauge-only two-loop G422 running is DERIVED/VERIFIED as an engineering calculation; the claimed first-principles heavy-threshold derivation is OPEN / UNDERDETERMINED.**

The historical `0.71%` threshold-repair claim is superseded.

## L4 — microscopic partial-trace derivation of T^(I)_mu_nu

Claim tested: derive the informational effective stress tensor and all phenomenological coefficients from a specified microscopic deterministic theory by an explicit coarse-graining/partial trace.

The classical/effective-field-theory statement is valid conditionally: for a specified effective action `Gamma[g,I]`,

`T^(I)_mu_nu = -(2/sqrt(-g)) delta Gamma / delta g^(mu nu)`.

Likewise, integrating out microscopic modes can formally be written as

`exp(i Gamma[g,Psi_<]) = integral D Psi_> exp(i S_micro[g,Psi_<,Psi_>])`.

But this is a definition/formal construction, not microscopic closure. The present theory does not specify enough information to compute `Gamma` uniquely: the microscopic degrees of freedom, state/measure, coarse-graining map, regulator/renormalization prescription, or the resulting Wilson coefficients are not frozen. Generic integration also generates additional covariant operators (`R^2`, `R_mu_nu R^mu_nu`, derivative interactions, running nonminimal coupling, etc.), so the claim that only `xi_I=1/6` plus classical scalar terms remain does not follow.

**Terminal verdict: L4 = PARTIAL. Classical metric variation is DERIVED; microscopic partial-trace origin and coefficient determination are OPEN / UNDERDETERMINED.**

## Global dependency audit

Current non-circular verified/conditional chain:

`frozen G422 spectrum registry -> gauge beta coefficients -> gauge-only two-loop (M_I,M_U,alpha_U)`

Current still-circular or externally constrained chain:

`target beta -> Lambda_X -> mu_I` in the historical manuscript.

For a true prediction the direction must be:

`frozen UV action -> protected mu_I -> Lambda_X -> beta`.

That upstream protection is not derived, so `beta ~= 1e-15` remains conditional rather than parameter-free.

The dark values `(lambda_phi,v_phi)` remain fitted/constrained. The threshold and proton-decay results remain blocked on a frozen heavy spectrum. The microscopic informational back-reaction remains an EFT/formal statement rather than a derived microscopic result.

## Terminal closure matrix

| Limitation | Terminal status | Result |
|---|---|---|
| L1 | OPEN / UNDERDETERMINED | Several simple protection branches falsified; no explicit surviving UV protection mechanism derives `mu_I`. |
| L2 | FAIL + OPEN | Minimal 102 GeV portal fails; replacement non-minimal SO(10) dark sector is unspecified. |
| L3 | PARTIAL | Gauge-only two-loop G422 running verified; derived heavy thresholds remain open. |
| L4 | PARTIAL | Classical stress tensor derivable; microscopic partial-trace coefficient closure remains open. |

## Stop condition

The L1–L4 audit is complete for this conversation. New nonlinear protection models, new dark-sector models, full heavy-spectrum derivations, and microscopic deterministic constructions are separate future research branches and must be versioned as such. They are not prerequisites for closing this conversation.

No L1–L4 claim is promoted beyond the evidence above.