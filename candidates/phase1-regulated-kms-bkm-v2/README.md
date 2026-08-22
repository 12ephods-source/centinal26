# Phase I Regulated KMS–Modular–Cocycle/BKM Falsification Harness

Status: `EXPERIMENTAL`

This candidate restores the missing KMS/relative-entropy/BKM layer on top of the current merged Phase-I finite-regulator lineage. It is a NumPy-only finite Type-I falsification harness. A numerical PASS is claim-scoped and does not establish continuum factor type, emergent geometry, a continuum Connes cocycle, or gravitational canonical-energy equivalence.

## Canonical type chain

The analytic target remains

\[
\mathcal M_O\;\text{Type }\mathrm{III}_1
\to
\mathcal M_O\rtimes_{\sigma^{\omega_0}}\mathbb R\;\text{Type }\mathrm{II}_\infty
\to
\Pi\mathcal N\Pi\;\text{Type }\mathrm{II}_1,
\]

where the final finite corner is obtained only through the regulated CLPW positive-energy projection. Finite matrices do not prove this classification.

## Frozen analytic normalization

\[
\beta_{\rm dS}=2\pi L,
\qquad
L=1\;\text{in numerical units},
\qquad
\rho_0=Z^{-1}e^{-\beta_{\rm dS}H_{\rm st}}.
\]

Thus

\[
K_{\rm mod}=-\log\rho_0=\beta_{\rm dS}H_{\rm st}+cI,
\]

and

\[
\sigma_s^{\rho_0}(A)=\alpha^{\rm st}_{-\beta_{\rm dS}s}(A).
\]

For coherent displacements,

\[
S(\rho_\epsilon\Vert\rho_0)=\beta_{\rm dS}\epsilon^2\sum_k\omega_k|f_k|^2,
\qquad
\mathcal F_{\rm BKM}=2\beta_{\rm dS}\sum_k\omega_k|f_k|^2.
\]

No normalization constant is fitted.

## Deterministic contract

The JSON schema is `frost.phase1.regulated-kms-modular-cocycle-falsification.v2` and freezes:

- `seed = 0`, with `randomness_used = false`;
- sorted JSON keys;
- explicit `L=1` and `beta_dS_formula = 2*pi*L`;
- all finite truncations, finite-difference amplitudes, modular parameters and cocycle perturbations;
- all gate thresholds;
- source and configuration SHA-256 provenance.

The seed is reserved only to make the machine-readable contract explicit. The harness does not call an RNG.

## Regulator lineage

This candidate does not pretend to reproduce already-qualified clock work. It records the merged upstream evidence:

- clock-regulator convergence: `58ca997a234ed0010fef30496ec4bbd4b7e99949`;
- finite Type-I cocycle consistency: `11912a736c9a5e10828bc281af32e389b5c5a33b`;
- bounded multi-mode cocycle regulator: `53698deea8bf002bd502f90a8bef35da37a72e37`.

It independently adds BKM truncation convergence (`n_cut=4,5,6`) and finite-difference refinement (`epsilon=0.20,0.10,0.05,0.025`).

## Gate accounting

- **Gate 1 — Geometric Reference Model:** finite KMS/modular reference proxy only; continuum Type III1 is not established.
- **Gate 2 — Quantum Clock Constraint Invariance:** upstream verified regulator evidence from the merged clock-regulator gate.
- **Gate 3 — Crossed-Product Algebra and Type:** finite Type-I cocycle surrogate only; continuum factor type remains an analytic target.
- **Gate 4 — Relative-Entropy/BKM Matter-Energy Baseline:** canonicalized in schema v2 because no prior separate historical Gate-4 definition was recovered. It tests matter modular/Killing-energy identities only and cannot establish gravitational canonical energy.
- **Gate 5:** `PROPOSED`.
- **Gate 6:** `PROPOSED`.

## Reproduce

```bash
python -m pip install -r candidates/phase1-regulated-kms-bkm-v2/requirements.txt
python candidates/phase1-regulated-kms-bkm-v2/harness.py --strict --output phase1-kms-bkm.json
python -m unittest discover -s candidates/phase1-regulated-kms-bkm-v2 -p 'test_*.py' -v
```

Local pre-publication validation of this exact numerical model returned `PASS_REGULATED_KMS_MODULAR_COCYCLE_BKM_BASELINE`, with all six strict numerical gates passing. GitHub CI must independently reproduce the result before promotion.

© 2026 Robert Frost
