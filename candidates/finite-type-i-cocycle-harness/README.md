# Finite Type-I Cocycle Consistency Harness

Status: `EXPERIMENTAL`

This candidate follows the validated clock-regulator convergence gate. It tests only finite-dimensional matrix-algebra identities and their compatibility with the resolved finite GNS/clock regulator.

## Algebraic object under test

For faithful finite-dimensional density matrices `rho1` and `rho0`,

\[
u_s = \rho_1^{is}\rho_0^{-is},
\]

with modular flow

\[
\sigma_s^\rho(A)=\rho^{is}A\rho^{-is}.
\]

The finite-Type-I cocycle identity is

\[
u_{s+t}=u_s\,\sigma_s^{\rho_0}(u_t).
\]

The harness verifies:

- faithful support with no eigenvalue clipping/flooring;
- `u_0=I`;
- cocycle unitarity;
- cocycle chain rule;
- modular group composition;
- state modular-flow transport;
- zero-perturbation control;
- nontrivial perturbed-state mismatch;
- persistence of that mismatch after the resolved clock readout;
- nonvanishing observable retention;
- detuned, nonresonant `T-delta_q` scaling;
- a separate full-line clock regulator followed by `Pi=Theta(q)`, so projection leakage is a genuine diagnostic rather than a tautological zero.

## Clock-regulator boundary

The resolved clock grid inherits the previous gate's condition

\[
T\Delta q\ll 1,
\]

and avoids exact arithmetic resonance for

```text
omega in {1.00, 1.01, 1.03}
```

The finite cocycle is then tested before and after the regulated readout.

## Projection cross-check

The ordinary positive-grid POVM build has positivity built into its Hilbert space. Its projection leakage is therefore tautologically zero.

This candidate additionally constructs a periodic full-line energy grid, prepares a localized positive-energy wavepacket, translates it unitarily, and measures

\[
\lVert (I-\Pi)U\Pi\psi\rVert^2,
\qquad \Pi=\Theta(q).
\]

The leakage must be nonzero at a deliberately coarse cutoff and decay strongly as the positivity boundary is moved away from the packet.

## Reproduce

```bash
python -m pip install -r candidates/finite-type-i-cocycle-harness/requirements.txt
python candidates/finite-type-i-cocycle-harness/cocycle_scan.py \
  --strict \
  --output finite-type-i-cocycle.json
python -m unittest discover \
  -s candidates/finite-type-i-cocycle-harness \
  -p 'test_*.py' \
  -v
```

GitHub Actions runs the same strict gate on Python 3.11, 3.12, and 3.13.

## Interpretation boundary

A passing result means only:

```text
PASS_FINITE_TYPE_I_COCYCLE_CONSISTENCY
```

It does **not** establish a genuine crossed-product Type-II factor, a Type-III algebra, or a continuum Connes Radon-Nikodym cocycle for the de Sitter theory. The continuum status remains:

```text
BLOCKED_NOT_ESTABLISHED_BY_FINITE_MATRICES
```

Any continuum-motivated construction after this must be treated as a new separately falsifiable regulator hypothesis.

© 2026 Robert Frost
