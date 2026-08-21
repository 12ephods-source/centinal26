# Two-Mode Finite Type-I Cocycle Stress Test

Status: `EXPERIMENTAL`

This candidate is the first bounded expansion after the merged single-mode finite-Type-I cocycle gate. It does not represent a field algebra.

## Added stressors

The finite Hilbert space contains two truncated oscillators with reference Hamiltonian

\[
H_0=\omega_1N_1+\omega_2N_2.
\]

The perturbed state uses local displacements plus a weak non-factorizing interaction,

\[
H_1=H_0+\frac{\kappa}{\sqrt2}(\omega_1X_1+\omega_2X_2)
+g\sqrt{\omega_1\omega_2}X_1X_2.
\]

The `X1 X2` term is deliberately a numerical stress-test interaction. It is not claimed to be a derived de Sitter coupling.

## Required checks

The harness verifies finite cocycle unitarity, chain rule, modular-group composition, state transport, faithful density support, and density normalization. It also requires the `g=0` cocycle to agree with the tensor product of the independently constructed one-mode cocycles, while `g>0` must measurably break that factorization.

The interacting modular mismatch is then passed through the resolved clock regulator using detuned frequency pairs and `T*delta_q` refinement. Residual improvement is not accepted if the observable is annihilated.

## Frequency pairs

```text
(1.00, 1.37)
(1.01, 1.37)
(1.03, 1.41)
```

These are bounded stress controls, not a field-mode range.

## Reproduce

```bash
python -m pip install -r candidates/two-mode-cocycle-stress/requirements.txt
python candidates/two-mode-cocycle-stress/two_mode_scan.py \
  --strict \
  --output two-mode-cocycle.json
python -m unittest discover \
  -s candidates/two-mode-cocycle-stress \
  -p 'test_*.py' \
  -v
```

GitHub Actions runs the strict gate on Python 3.11, 3.12, and 3.13.

## Interpretation boundary

A passing result authorizes only a further **bounded multi-mode regulator test**. It does not establish a field theory limit, Type-II/III operator algebra, or continuum Connes cocycle.

The continuum status remains

```text
BLOCKED_NOT_ESTABLISHED_BY_FINITE_MATRICES
```

© 2026 Robert Frost
