# FToE SO(10) → 422 → SM Closure State

Status: **REVIEW**

This branch replaces the previously assumed direct `SO(10) -> SM` unification path with a falsification-gated candidate chain

\[
SO(10) \xrightarrow{210_H} SU(4)_C\times SU(2)_L\times SU(2)_R \xrightarrow{126_H} G_{SM}.
\]

It does not promote the repaired branch to a prediction. Numerical execution, naturalness, group-theoretic closure, threshold closure, and scientific closure are separate gates.

## Corrected low-energy spectrum

The informational scalar is treated as a complex electroweak doublet

\[
I\sim(1,2,+1/2)
\]

with provisional physical threshold

\[
m_I=\sqrt{2}\,\mu_I\approx 13.5\ \mathrm{TeV}.
\]

For one additional complex Higgs-like doublet, the one-loop contribution is

\[
\Delta b=(1/10,1/6,0),
\]

not the previously used hypercharge contribution `5/18`.

Thus above `m_I`

\[
(b_1,b_2,b_3)=(21/5,-3,-7).
\]

The direct SM + I one-stage unification branch is therefore classified **FAIL**.

## Two-loop 422 gate

The validated gauge-only two-loop branch uses the independently audited `G422` coefficient set and activates the informational doublet only above its physical threshold. The current certified root is approximately

\[
M_I=7.03749\times10^9\ \mathrm{GeV},\qquad
M_U=2.04991\times10^{16}\ \mathrm{GeV},
\]

\[
\alpha_U=0.0320673,
\]

with inverse-coupling spread near `2e-11`. The reference 2HDM+G422 branch is reproduced before this FToE-specific result is accepted.

## Informational hierarchy scan

Once `M_U` is derived, the code scans

\[
\mu_I^2=c_n C_{\rm eff} M_U^2\left(\frac{M_U}{M_P}\right)^n
\]

rather than fixing `n` in advance. At the current gauge-only `M_U`, the closest order-one solution is

\[
n=9,\qquad d_{op}=13,\qquad c_9C_{\rm eff}\approx2.04.
\]

This is only a dimensional candidate until the explicit SO(10) contraction and `C_eff` are derived.

## Renormalizable naturalness obstruction

A more basic gate precedes the dimension-13 operator search. For an ordinary informational multiplet `I` and a GUT-breaking scalar `Phi`, the renormalizable norm portal

\[
(I^\dagger I)(\Phi^\dagger\Phi)
\]

is automatically gauge invariant. Ordinary phase symmetries acting on `I` cannot forbid it because `I^dagger I` is neutral. After `Phi` acquires a GUT-scale VEV,

\[
\delta\mu_I^2\sim\lambda_{I\Phi}M_U^2.
\]

Keeping `mu_I = 9.54 TeV` at the verified `M_U` requires approximately

\[
\lambda_{I\Phi}\lesssim\left(\frac{\mu_I}{M_U}\right)^2
\approx2.17\times10^{-25}.
\]

Therefore the branch in which `I` is merely a conventionally embedded light component of `10_H`, `126_H`, or another ordinary GUT scalar with no stronger protection is **FAIL** on technical naturalness grounds.

The surviving branch must demonstrate an exact or collective Goldstone/shift symmetry, sequestering, or an equivalently explicit mechanism that removes the renormalizable mass and portal terms and keeps them radiatively stable. `scripts/ftoe_so10_naturalness_gate.py` encodes this distinction. Its gauge-loop estimate `g_U^4/(16 pi^2)` is used only as an order-of-magnitude stability diagnostic, not as an exact mass correction.

This conclusion is consistent with standard SO(10) Higgs-sector analyses: conventional `10` and `126` electroweak doublets mix through a GUT-scale `210` VEV and require light-doublet fine tuning in the minimal renormalizable construction; nonsupersymmetric SO(10) pseudo-Goldstone directions can receive loop corrections of order `M_G^2/(16 pi^2)` when the relevant accidental symmetry is explicitly broken.

## Selection-rule gate

The executable charge algebra additionally proves:

- ordinary phase `Z_N` symmetries cannot forbid `I^dagger I`;
- conventional shared-Yukawa assignments force the `10_H 126_H 210_H` charge neutral;
- a `Z_11` selector can postpone the chosen `B_3 S^k` spurion tower to dimension 13, but this is not an exhaustive SO(10) tensor-invariant proof.

Hence a separate informational sector is required for the current protection strategy, and its full scalar potential must be specified before L1 can close.

## Downstream informational transition

The conditional tail remains

\[
-\mu_I^2+\frac{7.31\xi_I}{2}\frac{\Lambda_X^4}{M_P^2}=0,
\qquad \xi_I=1/6,
\]

followed by

\[
\beta=(\Lambda_X/M_P)^2.
\]

This arithmetic is not a first-principles prediction until `mu_I` survives the naturalness and operator gates.

## Fail-closed gates

The implementation remains **REVIEW** while any of these remain unresolved:

- exact protected informational multiplet and symmetry realization;
- radiative stability of that protection;
- explicit SO(10)-singlet mass-generating operator and Clebsch factor;
- exhaustive exclusion or suppression of lower-dimensional breaking operators;
- full heavy threshold spectrum derived from the same scalar potential;
- two-loop + derived-threshold re-solution;
- proton-decay calculation from the same frozen heavy spectrum.

A software PASS must never be interpreted as a scientific PASS.

## Current decision

- Historical direct unification: **FAIL**.
- Intermediate non-D-parity 422 gauge branch: **PASS as gauge-only calculation / REVIEW as theory**.
- Simple embedded informational doublet without extra protection: **FAIL**.
- Protected pNGB/sequestered informational branch: **ACTIVE / REVIEW**.
- Dimension-13 hierarchy: **candidate only**.
- L1 informational-mass derivation: **REVIEW with the unprotected branch excluded**.
- L3 threshold/unification closure: **REVIEW**.
- Proton-decay point prediction: **BLOCKED**.

No parameter may be changed after inspecting an observable it is intended to predict.
