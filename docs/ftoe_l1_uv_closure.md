# FToE L1 UV-closure candidate

Status: **REVIEW**. Numerical hierarchy and selection-rule compatibility are implemented; a complete SO(10) vacuum and explicit pNGB coset are not yet derived.

## Frozen target

- `M_G = 2.43e16 GeV`
- `M_P = 1.22089e19 GeV`
- `mu_I = 9.53e3 GeV`
- `xi_I = 1/6`
- transition coefficient `7.31`

The required hierarchy is

`mu_I^2 / M_G^2 ~= 1.54e-25`.

Scanning `mu_I^2 = c_n M_G^2 (M_G/M_P)^n` selects `n=9`, with `c_9 ~= 0.314`, as the closest order-one Wilson coefficient.

## Candidate architecture

1. Embed the informational electroweak doublet as a linear combination of weak-doublet components in an SO(10) Higgs sector containing `10_H`, `126_H`, `bar126_H`, and `210_H`.
2. Protect the light direction by an enhanced/pNGB symmetry. An ordinary phase `Z_N` is **not** sufficient because `I^dagger I` is neutral.
3. Require a sole explicit-breaking spurion `S` carrying unit charge under `Z_9`.
4. `Z_9` forbids `S^k` for `k=1..8` and allows `S^9`.
5. A schematic dimension-13 breaking invariant then has the scaling

   `O_13 / M_P^9 ~ (I mass-breaking structure) S^9 Sigma^2 / M_P^9`.

   For `<S> ~ <Sigma> ~ M_G`, it generates

   `mu_I^2 ~ c_9 M_G^11/M_P^9`.

This is a **selection-rule candidate**, not yet a demonstrated SO(10) tensor contraction.

## Anomaly boundary

If `Z_9` charges only scalar spurions and all chiral fermions are neutral, the usual chiral mixed gauge-anomaly sums receive no scalar contribution. This closes only that perturbative anomaly sub-gate. A discrete-gauge UV origin, gravitational consistency, and any embedding into an anomaly-free continuous parent symmetry remain REVIEW.

## External representation evidence

Primary literature used to constrain the candidate:

- Chen, Zhang, Bai, *Couplings in Renormalizable Supersymmetric SO(10) Models*, arXiv:1707.00580 — computes renormalizable couplings among `10`, `126 + bar126`, `45`, `54`, and `210` using `SU(5) x U(1)_X` decomposition.
- Tavartkiladze, *Light Pseudo-Goldstone Higgs Boson from SO(10) GUT with Realistic Phenomenology*, arXiv:1803.11164 — explicit SO(10) precedent for a symmetry-protected light pseudo-Goldstone doublet; supersymmetric, so mechanism evidence only.

## Gates

- weak doublet exists in candidate SO(10) sectors: `EXTERNAL_SOURCE_PASS`
- `10 x 126 x 210`-type mixing structures exist: `EXTERNAL_SOURCE_PASS`
- minimal `45 + 126 + 10` natural implementation: `FAIL` for this FToE closure route
- dimension-13 hierarchy arithmetic: `PASS`
- `mu_I -> Lambda_X -> beta` numerical chain: `PASS`
- `Z_9` lower spurion powers 1..8 excluded: `PASS_CONDITIONAL`
- chiral mixed anomaly with scalar-only selector: `PASS_CONDITIONAL`
- explicit protecting pNGB symmetry/coset: `NOT_TESTED`
- exact SO(10) singlet contraction for the dimension-13 operator: `NOT_TESTED`
- full vacuum and doublet mass matrix: `NOT_TESTED`
- GUT thresholds and proton-decay backreaction: `NOT_TESTED`

Overall L1 status remains **REVIEW**. No numerical PASS may upgrade the scientific state while the last four gates are open.
