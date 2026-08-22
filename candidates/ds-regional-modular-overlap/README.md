# dS2 Regional Modular-Overlap Obstruction Harness

Status: `EXPERIMENTAL`

This candidate is stacked on the geometry-bearing dS2 relational baseline in PR #102. It tests the specific multi-observer issue that emerged from the Dynamical Relational Monism program: whether a nominal common regional algebra is preserved by the modular flows induced by neighboring observer states.

The harness is deliberately finite Type I. Its purpose is to produce a controlled **positive control** and **obstruction control**, not to claim a continuum regional-algebra theorem.

## Geometry-derived three-region model

The parent dS2 harness validates the stretched static patch

\[
ds^2=\operatorname{sech}^2x(-dt^2+dx^2)
\]

and the finite-difference spatial operator for a massless conformal scalar. This gate takes the `N_site=3` finite-difference kernel at `X=4` and quantizes a three-site truncated oscillator chain

\[
A-B-C.
\]

The Hamiltonian is

\[
H=\frac12\sum_i p_i^2+\frac12\sum_{ij}K_{ij}q_iq_j,
\]

with `K` inherited from the dS2 finite-difference operator. Each site has `N_cut=3`, so the complete Hilbert space has dimension 27. The thermal reference uses

\[
\rho=Z^{-1}e^{-2\pi H}.
\]

Two neighboring observer regions are represented by the reduced states on `AB` and `BC`; their nominal common observable algebra is the middle site `B`.

## Split-state control

At coupling fraction zero, the off-diagonal entries of `K` are removed. The thermal state factorizes across sites. In that case the harness requires a `B`-local observable to remain in the `B` subalgebra under both regional modular flows.

For the split `AB` state it also constructs the explicit state-preserving conditional expectation

\[
E_{AB\to B}(X)
=1_A\otimes(\omega_A\otimes\mathrm{id}_B)(X)
\]

and independently checks:

- state preservation;
- idempotence;
- the `B`-bimodule property.

This is the positive control.

## Correlated geometry state

The coupling fraction is then scanned through

`{0, 0.25, 0.5, 0.75, 1}`.

At full coupling, the state is the thermal state of the actual three-site dS2 finite-difference chain. The harness computes mutual information and tests a `B`-local quadrature under

\[
\sigma_s^{\rho_{AB}},\qquad \sigma_s^{\rho_{BC}},
\]

for `s={-0.25,-0.125,0.125,0.25}`.

Leakage is the Hilbert-Schmidt distance to the nominal `B` subalgebra after modular evolution. A successful obstruction test requires leakage to be negligible in the split control but decisively nonzero in the correlated geometry state.

That is the correct behavior for this gate: **correlation-induced failure of naive overlap preservation is a PASS**, because the program is testing the obstruction rather than assuming that all observer patches glue by equality.

## Strict gates

- `REG1` — split state preserves the overlap algebra under modular flow.
- `REG2` — split state admits the explicit state-preserving conditional expectation.
- `REG3` — the full geometry-derived state has nonzero regional mutual information.
- `REG4` — the correlated state produces nontrivial modular leakage from the nominal overlap algebra.
- `REG5` — left/right obstruction agrees under reflection symmetry of the three-site geometry.
- `REG6` — all finite density matrices used by modular flow remain faithful.

## Scope boundary

A PASS does **not** establish:

- a continuum modular-inclusion theorem;
- a Type-II or Type-III regional algebra;
- a unique global gluing law;
- spacetime reconstruction from the overlap network.

It establishes only that the geometry-derived finite surrogate reproduces the qualitative distinction required by the research program: compatible split inclusions versus correlation-induced modular obstruction.

## Reproduce

```bash
python -m pip install -r candidates/ds-regional-modular-overlap/requirements.txt
python candidates/ds-regional-modular-overlap/regional_modular_overlap_scan.py \
  --strict \
  --output ds-regional-modular-overlap.json
python -m unittest discover \
  -s candidates/ds-regional-modular-overlap \
  -p 'test_*.py' \
  -v
```

© 2026 Robert Frost
