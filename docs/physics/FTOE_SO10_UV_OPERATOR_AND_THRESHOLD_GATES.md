# FToE SO(10) UV Operator and Threshold Gates

Status: **REVIEW**. This document records executable closure gates; it is not a claim that the UV completion has been derived.

## Frozen numerical input from the repaired gauge branch

The current gauge-only two-loop `SO(10) -> G422 -> SM` calculation with the informational doublet turning on at `m_I = 13.4916 TeV` gives approximately:

- `M_I = 7.03749e9 GeV`
- `M_U = 2.04991e16 GeV`
- `alpha_U = 0.0320673`
- inverse-coupling spread at the root `~2.04e-11`

The reference 2HDM regression reproduces the published numerical neighborhood before this FToE-specific threshold is accepted.

## L1 charge-algebra results

### 1. Ordinary phase symmetry cannot protect a scalar norm mass

For any cyclic phase symmetry `Z_N`, if a scalar representation `R` has charge `q`, then

`q(R^dagger R) = -q + q = 0 mod N`.

Therefore a small informational mass cannot be protected merely by assigning a `Z_N` charge to the scalar multiplet. The protection must be an enhanced/accidental/shift-type symmetry whose Goldstone limit removes the mass term; a discrete selector may then control explicit breaking spurions.

### 2. Shared-Higgs Yukawa-compatible `Z_N` no-go

Assume the conventional renormalizable structures remain allowed:

- `16_F 16_F 10_H`
- `16_F 16_F bar126_H`
- `126_H bar126_H`
- `210_H^2`
- `210_H^3`

Writing `q(16_F)=x`, the first three imply

- `q(10_H) = -2x`
- `q(bar126_H) = -2x`
- `q(126_H) = +2x`.

The simultaneous conditions `2 q(210_H)=0` and `3 q(210_H)=0` imply `q(210_H)=0` for every cyclic `Z_N`. Hence

`q(10_H 126_H 210_H) = -2x + 2x + 0 = 0`.

So the same multiplets used for conventional Yukawa/Higgs structure cannot use a simple cyclic charge to postpone this cubic mixing to high operator dimension. A clean escape requires a distinct informational multiplet sector or a different symmetry architecture.

## Preferred hierarchy order

The executable hierarchy scan uses

`mu_I^2 / M_U^2 = (c_n C_eff) (M_U/M_P)^n`

with `mu_I = 9.54 TeV`, `M_P = 1.22089e19 GeV`, and the independently calculated `M_U` above. The current best integer power is

`n = 9`,

corresponding schematically to a dimension-13 mass-generating operator and requiring an order-one product `c_9 C_eff`.

The code intentionally reports `c_n C_eff`, not a Wilson coefficient alone. `C_eff` depends on the actual SO(10) tensor contraction and the protected light eigenvector and has not been calculated.

## Spurion selector

For a selected cubic SO(10) invariant `B_3` and singlet spurion `S`, the tower is `B_3 S^k`. A `Z_11` example with `q(B_3)=q(S)=1` makes the first neutral member occur at `k=10`, i.e. operator dimension `3+10=13`.

This proves only that the **chosen spurion tower** can be delayed to dimension 13. It does not prove that all other SO(10)-invariant operators of lower dimension are absent.

## Group-theory gate still open

Primary SO(10) group-theory literature explicitly treats the renormalizable Higgs representations `10`, `126`, `bar126`, `210` and their Clebsch-Gordan coefficients/mass matrices. Those results establish that the representation/coupling arena is legitimate, but they do not by themselves provide the FToE-specific protected pNGB eigenstate or the required dimension-13 invariant.

Required before L1 can pass:

1. freeze the exact informational representations (`10_I`, `126_I`, etc.);
2. write the full scalar potential and protecting symmetry;
3. prove a massless/light pNGB doublet exists in the exact-symmetry limit;
4. construct the explicit dimension-13 SO(10) singlet contraction;
5. compute its Clebsch factor and projection onto the pNGB eigenvector;
6. exhaustively enumerate lower-dimension symmetry-breaking invariants and show they are absent or sufficiently suppressed.

Until those steps are done, **L1 = REVIEW**.

## L3 heavy-threshold gate

`scripts/ftoe_so10_threshold_gate.py` takes a pre-frozen heavy spectrum JSON. For each multiplet `a`, it computes logarithmic one-loop matching contributions

`Delta_i = -(1/(2 pi)) sum_a b_i^(a) ln(M_a/M_match)`.

It then applies any separately declared finite matching constants and evaluates the final inverse-coupling spread.

Critical rule: the script does **not** optimize `M_a`. If the spectrum is not derived from the scalar potential before the residual is inspected, the scientific gate remains `NOT_TESTED`.

Required spectrum work:

- derive all heavy gauge and scalar masses from the same frozen `210_H/126_H/10_H` (+ informational) potential;
- attach the correct beta contribution to each Pati-Salam/SM multiplet;
- derive finite matching constants in one declared convention;
- run the threshold gate without retuning masses;
- propagate the same spectrum into proton decay.

Until this exists, **full L3 = REVIEW** even though the gauge-only two-loop crossing is numerically verified.

## Primary-source provenance

Relevant primary literature used as structural provenance:

- Z.-Y. Chen, D.-X. Zhang, X.-Z. Bai, *Couplings in Renormalizable Supersymmetric SO(10) Models*, arXiv:1707.00580 — general renormalizable couplings and CG coefficients for `10`, `126`, `bar126`, `210` and related representations.
- T. Fukuyama et al., *SO(10) Group Theory for the Unified Model Building*, arXiv:hep-ph/0405300 — states, CG tables and mass matrices for a broad `SO(10)` Higgs system including `10`, `126`, `bar126`, `210`.
- T. Fukuyama et al., *General Formulation for Proton Decay Rate in Minimal Supersymmetric SO(10) GUT*, arXiv:hep-ph/0401213 — complete Higgs mass matrices, threshold effects and proton-decay formulation in the `10 + 126 + bar126 + 210` setting.
- L. Graf et al., *One-loop pseudo-Goldstone masses in the minimal SO(10) Higgs model*, arXiv:1611.01021 — explicit demonstration that pNGB scalar masses in non-supersymmetric SO(10) require a controlled quantum vacuum analysis.

These sources establish available machinery, not the truth of the FToE completion.
