# FToE L1 UV-closure clean successor — 2026-08-22

This ports the bounded five-file scientific module from stale PR #109 onto current `main` without merging its divergent branch history.

PR #109 exact head `1e334dfac5bf8e3f46d84e36d63406bc01808875` did not qualify repository-wide: `validate` and `federation-gates` passed, while CI, automation-gates, and Mature Product Qualification failed at lint before the test suite. The first concrete failure was Ruff `B008` in `evaluate_l1`, caused by constructing `L1Inputs()` in a function default argument.

The clean successor preserves the frozen numerical and epistemic semantics while fixing only that implementation defect by using a `None` default and constructing `L1Inputs()` inside `evaluate_l1`.

Preserved scientific state:
- dimension-13 hierarchy arithmetic is a numerical compatibility check, not a derivation of the SO(10) operator;
- the `mu_I -> Lambda_X -> beta` numerical chain is not a UV derivation;
- Z9 is only a candidate spurion selector and is not itself mass protection;
- explicit protecting symmetry/coset, exact SO(10) singlet contraction, full vacuum/doublet mass matrix, threshold backreaction, and proton decay remain open;
- overall L1 state remains `REVIEW` unless every mandatory UV gate is independently satisfied.

This successor is independent of the broader exact-head-green PR #105 closure lineage; the two historical branches diverged and are not treated as parent/child merely by chronology.
