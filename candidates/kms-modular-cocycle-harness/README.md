# KMS–Modular–Cocycle Falsification Harness

Status: `EXPERIMENTAL`

This NumPy-only candidate is the next finite-dimensional falsification layer after
`candidates/clock-regulator-harness/`. It is deliberately a **Type-I matrix
surrogate**. It tests exact thermal/modular identities, finite Type-I cocycle
identities, and the analytic coherent-displacement BKM baseline. It does not infer
a Type-II/Type-III algebra from finite matrices and does not test gravitational
canonical energy.

## Frozen conventions

The thermal reference state is

\[
\rho_0=Z^{-1}\exp(-\beta_{\rm dS}H_{\rm st}),
\qquad \beta_{\rm dS}=2\pi,
\]

with finite-dimensional modular convention

\[
\sigma_s^\rho(A)=\rho^{is}A\rho^{-is}.
\]

For the thermal reference state,

\[
\sigma_s^{\rho_0}(A)=\alpha^{\rm st}_{-\beta_{\rm dS}s}(A).
\]

The normalized trace is tested separately. Its modular flow must be trivial; the
harness never identifies trace modular flow with clock evolution.

The observer-clock target is the positive-energy construction

\[
\mathcal H_{\rm obs}=L^2(\mathbb R_+),\qquad H_{\rm obs}=q\ge0.
\]

Numerically this is represented only by a positive `q` grid and a smeared POVM
effect. No exact self-adjoint canonical time operator and no distributional
`|tau><tau|` clock observable is asserted.

## Coherent-displacement BKM unit test

For independent truncated oscillator modes,

\[
\rho_\epsilon=D(\epsilon f)\rho_0D(\epsilon f)^\dagger.
\]

The infinite-oscillator analytic baseline is

\[
S(\rho_\epsilon\Vert\rho_0)
=\beta_{\rm dS}\epsilon^2\sum_k\omega_k|f_k|^2,
\]

so

\[
\mathcal F_{\rm BKM}
=2\beta_{\rm dS}\sum_k\omega_k|f_k|^2.
\]

No normalization is fitted. The Hessian is evaluated by the central second
difference

\[
\mathcal F_{\rm BKM}(\epsilon)
\approx
\frac{S(\rho_{+\epsilon}\Vert\rho_0)
+S(\rho_{-\epsilon}\Vert\rho_0)}{\epsilon^2}.
\]

The harness separately checks

\[
S(\rho_\epsilon\Vert\rho_0)=\beta_{\rm dS}\Delta E_{\rm matter}.
\]

This is a matter modular/Killing-energy unit test only. It is not an identification
with Hollands–Wald canonical energy.

## Finite Type-I cocycle checks

For faithful density matrices on the same finite matrix algebra,

\[
u_s=(D\omega:D\omega_0)_s=\rho^{is}\rho_0^{-is}.
\]

The harness independently tests identity at `s=0`, unitarity, the cocycle identity
\(u_{s+t}=u_s\sigma_s^{\omega_0}(u_t)\), modular intertwining, the finite-dimensional
chain rule, and the derivative at `s=0` against
\(i(\log\rho-\log\rho_0)\). These are finite Type-I identities only; passing them
does not establish a continuum Connes Radon–Nikodym cocycle.

## Deterministic scans

The frozen numerical scan uses:

- `beta_dS = 2*pi`;
- frequencies `omega = {1.00, 1.03}`;
- displacement profile `f = {0.35+0.20j, -0.25+0.15j}`;
- truncations `n_cut = {3, 4, 5}`;
- finite-difference amplitudes `epsilon = {0.2, 0.1, 0.05, 0.025}`;
- cocycle stress amplitudes `{0.05, 0.1, 0.2}`;
- modular parameters `s = {-0.25, -0.125, 0.125, 0.25}`;
- positive clock grid `q in [0,8]`, `delta_q=0.25`, `sigma_tau/beta=1/16`.

The JSON report records every scan point, all thresholds, and source/configuration
SHA-256 provenance.

## Gate accounting

The original Phase-I names are preserved:

- **Gate 1 — Geometric Reference Model:** the finite thermal/KMS/modular proxy can
  pass; the continuum Type-III static-patch claim is not numerically verified by
  this harness.
- **Gate 2 — Quantum Clock Constraint Invariance:** this candidate rechecks the
  positive-energy smeared clock effect. Full clock-regulator convergence is a
  prerequisite supplied by PR #83.
- **Gate 3 — Crossed-Product Algebra and Type:** finite Type-I cocycle identities
  are testable here. Continuum type classification is an analytic target, not a
  conclusion drawn from finite matrices.
- **Gate 5:** `PROPOSED`.
- **Gate 6:** `PROPOSED`.
- Higher-order/nonlinear reconstruction remains a separate open gate.

The continuum target remains

\[
\mathcal N=\mathcal M_O\rtimes_{\sigma^{\omega_0}}\mathbb R
\quad\text{Type }\mathrm{II}_\infty,
\qquad
\Pi\mathcal N\Pi\quad\text{Type }\mathrm{II}_1,
\]

but this finite candidate does not attempt to prove that classification
numerically.

## Reproduce

```bash
python -m pip install -r candidates/kms-modular-cocycle-harness/requirements.txt
python candidates/kms-modular-cocycle-harness/kms_modular_cocycle_scan.py \
  --strict \
  --output kms-modular-cocycle.json
python -m unittest discover \
  -s candidates/kms-modular-cocycle-harness \
  -p 'test_*.py' \
  -v
```

## Current local validation

The pre-publication local run returned:

| Diagnostic | Result |
|---|---:|
| Overall status | `PASS_FINITE_TYPE_I_KMS_MODULAR_COCYCLE_BASELINE` |
| Strict finite gates | `9/9 PASS` |
| Regression tests | `8/8 PASS` |
| Analytic \(\mathcal F_{\rm BKM}\) | `3.1422209721205103` |
| Max `n_cut=5` BKM relative error | `3.07e-10` |
| `epsilon 0.05 -> 0.025` BKM refinement change | `5.28e-12` |
| Max `|S-beta*DeltaE|` | `1.11e-15` |
| Max cocycle algebraic residual | `1.13e-15` |
| Max cocycle-generator relative error | `1.35e-10` |
| KMS boundary residual | `0.0` |
| Clock POVM closure residual | `5.27e-15` |

The next admissible advance is a conformal-scalar/de Sitter-diamond model and then
a regulated relational embedding `j_tau`. No BKM-to-gravitational-canonical-energy
optimization is authorized by this result.

© 2026 Robert Frost
