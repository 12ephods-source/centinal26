# Clock-Regulator Convergence Harness

Status: `EXPERIMENTAL`

This NumPy-only harness tests the finite-dimensional Type-I GNS/clock regulator used
as a surrogate for a relational observable construction. It computes all residuals
from matrix elements, detects arithmetic lattice locking, and separates finite
regulator consistency from claims about continuum Type-II/Type-III algebras.

## Scope

The matter model is one truncated oscillator mode,

\[
L_{\mathrm{st}}=H\otimes I-I\otimes H^T,
\qquad
A_X=\frac{a+a^\dagger}{\sqrt2}\otimes I,
\]

with a positive uniform clock-energy grid. The clock effect is

\[
[E_{\sigma,\tau}]_{jk}
=\frac1P e^{-i(q_j-q_k)\tau}
e^{-\frac12\sigma_\tau^2(q_j-q_k)^2},
\qquad P=\frac{2\pi}{\Delta q}.
\]

The Gaussian group-average filter is applied in the diagonal basis of the total
constraint:

\[
[\mathcal G_T(X)]_{mn}
=e^{-\frac12T^2(c_m-c_n)^2}X_{mn}.
\]

The reported diagnostics are

\[
\frac{R_C}{\omega}
=\frac{\lVert[C,\mathcal R(A)]\rVert_F}
       {\omega\lVert\mathcal R(A)\rVert_F},
\qquad
R_{\mathrm{int}}
=\frac{\lVert\mathcal R_\tau(\alpha_{-\beta s}A)
-\mathcal R_{\tau-\beta s}(A)\rVert_F}
{\lVert\mathcal R_\tau(\alpha_{-\beta s}A)\rVert_F}.
\]

## Why the joint regulator scan is necessary

At the old locked grid, `omega=1`, `delta_q=0.25`, and `T=2*beta`, exact arithmetic
resonances survive while neighboring differences are under-resolved. This gives the
false-positive value

```text
R_C/omega = 0.00253748024486261
```

Halving `delta_q` at fixed `T` moves toward the resolved finite-`T` result instead of
toward zero:

```text
delta_q = 0.125
R_C/omega = 0.047636473042011
```

The harness therefore scales `T` and `delta_q` together, enforces
`T*delta_q <= eta_target`, and avoids exact resonance for all stress frequencies
`omega in {1.00, 1.01, 1.03}`. The correct resolved asymptotics are

\[
\frac{R_C}{\omega}\longrightarrow
\frac{1}{\sqrt2\,T\omega},
\qquad
R_{\mathrm{int}}\longrightarrow
\sqrt{2\left(1-e^{-(\beta s)^2/(4T^2)}\right)}.
\]

Raw Frobenius retention falls approximately as `T**(-1/2)` in the resolved
continuum sequence. The stable nontriviality diagnostic is therefore
`sqrt(T/beta) * observable_retention`, not constant raw retention.

## Reproduce

```bash
python -m pip install -r candidates/clock-regulator-harness/requirements.txt
python candidates/clock-regulator-harness/clock_regulator_scan.py \
  --strict \
  --output candidates/clock-regulator-harness/results/host-validation.json
python -m unittest discover \
  -s candidates/clock-regulator-harness \
  -p 'test_*.py' \
  -v
```

`--strict` exits nonzero unless every gate passes. GitHub Actions runs the same
commands on Python 3.11, 3.12, and 3.13 and uploads each JSON report as evidence.

## Current host result

The checked-in report was generated on Python 3.12 with NumPy 2.3.5.

| Validation metric | Result |
|---|---:|
| Endpoint-free `R_POVM` | `4.50e-15` |
| Dense/compressed maximum discrepancy | `4.86e-17` |
| Maximum resolved `R_C` continuum relative error | `0.00321` |
| Maximum resolved `R_int` continuum relative error | `0.00311` |
| Maximum `eta=0.125 -> 0.0625` refinement change | `9.94e-05` |
| Resolved `q_max` residual span | `2.16e-04` |
| Overall status | `PASS_CONTINUUM_REGULATOR_SCALING` |

Passing this gate updates the next step only to
`READY_FOR_FINITE_TYPE_I_COCYCLE_TEST`. It does **not** establish a Type-II or
Type-III algebra, a Connes Radon-Nikodym cocycle in the continuum theory, or a
physical de Sitter observer construction.

## Files

- `clock_regulator_scan.py` — transparent matrix construction, compressed exact
  Frobenius evaluator, convergence scans, and strict gates.
- `test_clock_regulator_scan.py` — independent dense cross-check and regression
  tests.
- `results/host-validation.json` — full host execution evidence, including source
  and configuration SHA-256 hashes.
- `.github/workflows/clock-regulator-harness.yml` — automatic multi-version CI.

© 2026 Robert Frost

