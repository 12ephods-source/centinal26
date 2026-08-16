# Common-State Geometry Gate

Status: PROPOSED / falsification-first

## Hypothesis

Let a primitive state be `(A, omega)` (or finite regulator `(H, rho)`). Matter and geometry are initially independent observable maps

- `M: rho -> matter observables`
- `G: rho -> geometric observables`

The research claim under test is that both can arise from the same state without defining either through the desired gravitational field equation.

## Non-circularity invariant

The geometry map MUST NOT be defined as

`G = E^{-1}(8 pi G M)`

and MUST NOT use `S=A/(4 G hbar)` as its definition. Einstein dynamics, Newton's constant, Bekenstein-Hawking entropy, and a Planck-area spectrum are forbidden inputs to the geometry reconstruction gate.

## Gate sequence

### G0 Primitive state
Specify the state/algebra, perturbation family, reference state, regulator and provenance.

### G1 Matter channel
Recover matter response from state variation. In controlled modular examples require the entanglement first-law relation and independently normalized modular flow.

### G2 Independent geometry channel — CRITICAL
Construct `G(rho)` or at minimum `delta G(rho)` from state/algebraic information independently of `M` and gravitational equations. Candidate observables may include relative entropy, mutual-information structure, modular inclusion/intersection data, or BKM/Fisher information, but none is to be called a spacetime metric until reconstruction conditions are demonstrated.

### G3 Same-state cross-channel test
For identical perturbations `rho -> rho + delta rho`, compute matter and candidate geometry responses independently. Test whether an operator relation `E[delta g] = kappa delta<T>` exists. `kappa` is inferred, never fixed to `8 pi G`.

### G4 Dynamics identification
Only after G2/G3 pass, test whether `E` has linearized Einstein form or a distinguishable correction.

### G5 Planck-scale consequence
Only after G4, test whether `G hbar` and any area/information relation emerge. `Delta A=4 l_P^2 ln 2` is not evidence of an area spectrum unless discreteness is independently derived.

## Failure conditions

Strong common-state reconstruction FAILS if any of the following occurs:

1. Geometry reconstruction requires Einstein equations as an input.
2. Geometry is defined by Bekenstein-Hawking entropy rather than independently reconstructed.
3. The candidate `G` contains no reconstructible geometric information beyond relabeling state-space distances.
4. Cross-channel coupling is inserted by normalization or target fitting.
5. A claimed result is regulator-dependent and does not converge under the declared scan.

## Numerical discipline

Every numerical observable must have: definition -> implementation -> independent recomputation -> convergence scan. No hard-coded residuals, target-directed normalization, or post-hoc parameter adjustment.

## Relationship to existing harness

This gate is stacked on the finite Type-I KMS/modular/cocycle baseline. Passing that baseline establishes only regulated algebraic identities; it does not establish a state-geometry dictionary. The next implementation target is a discretized de Sitter-diamond matter model and a candidate geometry reconstruction interface whose outputs remain explicitly `CANDIDATE_GEOMETRY` until G2 passes.
