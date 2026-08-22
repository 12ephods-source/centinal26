# Common-State Geometry Reconstruction Gate

Status: `G0-G1 SATISFIED BY CANONICAL PARENTS / G2 FINITE TOPOLOGY CANDIDATE UNDER TEST / G3-G5 BLOCKED`

## Hypothesis

Let the primitive state be `(A, omega)` or, at finite regulator, `(H, rho)`. Matter and geometry are initially independent observable maps

- `M: rho -> matter observables`
- `G: rho -> candidate geometric observables`.

The research claim under test is that both can arise from the same state without defining either through the desired gravitational field equation.

## Non-circularity invariant

The geometry map MUST NOT be defined as

`G = E^{-1}(8 pi G_N M)`

and MUST NOT use `S=A/(4 G_N hbar)` as its definition. Einstein dynamics, Newton's constant as a target normalization, Bekenstein-Hawking entropy as a metric definition, and an assumed Planck-area spectrum are forbidden inputs to G2.

The true regulator lattice is forbidden input to the reconstruction algorithm. It may be used only after reconstruction for falsification/scoring.

## Gate sequence

### G0 Primitive state

Specify the state/algebra, perturbation family, reference state, regulator, and provenance.

Current parent: the canonical finite dS2 regional chain on `main`.

### G1 Matter channel

Recover matter response from state variation. In controlled modular examples require the entanglement first-law relation and independently normalized modular flow.

Current parents: canonical Phase-I KMS/modular/cocycle/BKM and clock-regulator chain.

### G2 Independent geometry channel — CRITICAL

Construct `G(rho)` or at minimum `delta G(rho)` from state/algebraic information independently of `M` and gravitational equations.

The first finite candidate reconstructs only **topological geometry**, not a spacetime metric:

1. compute all pairwise quantum mutual informations from `rho`;
2. construct the maximum-mutual-information spanning tree using only those state observables;
3. independently recompute a candidate edge set from the top `N_site-1` mutual-information edges;
4. derive graph geodesic distances from the reconstructed tree;
5. only then compare the reconstructed adjacency/distances with the withheld regulator lattice.

A PASS means only that this finite state contains enough independently extractable information to reconstruct the latent path topology under the frozen scans. It does not identify proper length, Lorentzian metric, curvature, continuum factor type, or gravitational dynamics.

#### Frozen finite-G2 falsification requirements

- exact path-adjacency reconstruction for `n_cut = {3,4,5}` at full geometry coupling;
- exact graph-distance reconstruction for the same cutoff scan;
- the independent top-edge oracle must agree with the spanning-tree reconstruction;
- weakest true-neighbor mutual information / strongest non-neighbor mutual information must be at least `1.5` at every qualified cutoff;
- split-state control must abstain rather than hallucinate geometry when all pairwise mutual information is below `1e-8`;
- nonzero coupling robustness at `coupling_fraction = {0.10,0.25,0.50,1.0}` for `n_cut=4`;
- deterministic site-permutation equivariance;
- product-local-unitary invariance of the mutual-information reconstruction to absolute defect `<=1e-10`.

Thresholds are frozen before GitHub CI. The topology family and target were already known during engineering, so this is a confirmatory finite numerical gate, not a blinded scientific preregistration.

### G3 Same-state cross-channel test

For identical perturbations `rho -> rho + delta rho`, compute matter and candidate-geometry responses independently. Test whether an operator relation `E[delta g] = kappa delta<T>` exists. `kappa` is inferred, never fixed to `8 pi G_N`.

Status: `BLOCKED` until a G2 geometry channel richer than topology is independently reconstructed.

### G4 Dynamics identification

Only after G2/G3 pass at the required level, test whether `E` has linearized Einstein form or a distinguishable correction.

Status: `BLOCKED`.

### G5 Planck-scale consequence

Only after G4, test whether `G_N hbar` and any area/information relation emerge. `Delta A=4 l_P^2 ln 2` is not evidence of an area spectrum unless discreteness is independently derived.

Status: `BLOCKED`.

## Failure conditions

Strong common-state reconstruction FAILS if any of the following occurs:

1. geometry reconstruction requires Einstein equations as an input;
2. geometry is defined by Bekenstein-Hawking entropy rather than independently reconstructed;
3. the candidate contains no reconstructible geometric information beyond relabeling state-space distances;
4. cross-channel coupling is inserted by normalization or target fitting;
5. a claimed result is regulator-dependent and does not converge under the declared scan;
6. the finite G2 algorithm receives the target lattice, coordinates, or target edge set before producing its candidate geometry;
7. an uninformative split/product state is forced to produce a geometry rather than returning `ABSTAIN_UNINFORMATIVE_STATE`.

## Numerical discipline

Every numerical observable must have: definition -> implementation -> independent recomputation -> convergence/robustness scan. No hard-coded residuals, target-directed normalization, or post-hoc parameter adjustment.

## Claim boundary

Finite G2 topology reconstruction, even if it passes, is not a continuum state-to-spacetime dictionary. Continuum modular inclusion, Type-II/III classification, metric scale, causal/Lorentzian structure, Hollands-Wald canonical energy, Einstein dynamics, and Planck-scale consequences remain separate gates.

© Robert Frost
