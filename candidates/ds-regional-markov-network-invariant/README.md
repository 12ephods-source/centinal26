# dS2 Regional Markov Network Invariant v1

Status: `EXPERIMENTAL / CANDIDATE`

This gate follows the current-main regional modular-overlap obstruction baseline. The parent result shows that correlated dS2 finite-regulator states can obstruct naive preservation of a shared regional algebra under neighboring modular flows. The present candidate asks whether a complementary **state-only** obstruction quantity has a stable local-Hilbert-cutoff trend.

The candidate invariant is

\[
\mathcal I_{\rm net}=\sum_i I(i:i+2\mid i+1),
\]

the sum of conditional mutual informations over adjacent triplets of a four-site chain. It quantifies failure of an exact local quantum-Markov/recovery structure. It is dimensionless and invariant under product local unitaries.

The raw quadrature modular-leakage value is deliberately **not** used as the network invariant: exploratory cutoff scans showed substantial cutoff drift. That negative diagnostic is preserved rather than hidden by threshold relaxation.

## Qualification status

Thresholds in v1 were frozen after the exploratory cutoff study and before GitHub CI. Therefore a PASS is a current-source numerical/engineering qualification, **not** a blinded preregistered scientific confirmation.

Frozen gates:

1. split-state Markov control: `|I_net| <= 1e-10`;
2. fully coupled geometry state: `I_net >= 1e-3` at `n_cut=6`;
3. coupling scan at `n_cut=5` is strictly increasing;
4. reflection mismatch `<= 1e-10`;
5. cutoff refinement: relative `n_cut 5 -> 6` change `<= 0.10` and successive-difference contraction `<= 0.75`;
6. deterministic product-local-unitary invariance defect `<= 1e-10`.

The cutoff sequence is `n_cut={3,4,5,6}`. The full coupling-shape scan is evaluated at `n_cut=5`; endpoint refinement is evaluated at every cutoff to keep CI bounded.

## Claim boundary

Even a PASS establishes only a finite dS2 state-space candidate with a converging cutoff trend. It does not establish a continuum modular-inclusion theorem, Type-II/III factor classification, unique global gluing, spacetime reconstruction, Hollands-Wald canonical energy, or Einstein dynamics.

© Robert Frost
