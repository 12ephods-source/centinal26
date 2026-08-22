# Protected-I legacy reconciliation — 2026-08-22

This current-main reconciliation preserves the exact scientific state of the divergent protected-I branch chain without bulk-merging its historical implementation ancestry.

## Verified chain

- PR #281, head `0dbefff119005505ed733190ed29a19a70079dd2`: `ROLE_SEPARATED_REFERENCE_MECHANISM_STRUCTURALLY_SPECIFIED / REVIEW`; dedicated SO6 role-separation gate PASS.
- PR #285, head `dbde5d5aa0d971f901aca47c96e8f21a25038904`: `LOW_ENERGY_EW_GAUGE_QUANTUM_NUMBERS_COMPATIBLE_REFERENCE_ONLY / REVIEW`; dedicated EW embedding gate PASS.
- PR #288, head `c7b186e72d52adc981274ae77b18de9b5476bd2d`: `FAIL_Z2_ONLY_PORTAL_SUPPRESSION`; dedicated Z2 portal gate PASS.
- PR #295, head `904492673fe7ba73a4660702b1847581ceb1f21f`: `FAIL_MINIMAL_REFERENCE_PORTAL_SUPPRESSION`; dedicated Coleman-Weinberg portal, minimal disposition, and portal-scale relevance gates PASS.

These results are cumulative rather than contradictory: the SO6 reference can separate the two electroweak roles and match the low-energy gauge quantum numbers, but the role-separating Z2 does not forbid the norm portal, and the published minimal SO6 composite reference does not eliminate the generated mixed portal.

## Current mainline scientific boundary

PR #308, exact head `a20623e5e76c98abf2e1d37cebf04d09fc53e479`, is already merged at `3b9eff1e0eddcd27d0896067d457f34dca5ee736`. Its fail-closed verdict is:

`UNRESOLVED_UV_MATCHING_BIFURCATION / REVIEW_FAIL_CLOSED`

The smallest missing input remains an explicit versioned interaction/matching Lagrangian that retains distinct SM-Higgs and protected-I electroweak roles and derives their couplings or sequestering with the SO(10)-breaking `210_H`, `45_H`, `126_H`, and `10_C,H` sectors.

## Supersession rule

After this reconciliation is exact-head qualified and merged, PRs #281, #285, #288, and #295 may be closed as superseded records because their exact heads, transitions, qualification states, and fail-closed boundaries are preserved here. Closing those PRs does not erase or reverse their scientific results.

No claim is made of `mu_I`/13.5 TeV UV derivation, SO(10) sequestering closure, representation-specific radiative stability, portal elimination in an extended realization, or publication readiness.
