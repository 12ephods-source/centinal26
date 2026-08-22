# Bounded Multi-Mode Finite Type-I Cocycle/Regulator Stress

Status: `EXPERIMENTAL`

Dependency: `PASS_TWO_MODE_FINITE_TYPE_I_STRESS` at scientific head `a1212abf86ec85ff2d48f4c03db82efaf88a6456`.

This gate tests whether the already-validated finite Type-I cocycle and resolved-clock machinery remains numerically stable when expanded from two to three and four truncated modes. It deliberately remains finite dimensional.

## Frozen family

- mode counts: `2, 3, 4`
- per-mode truncation: `2`
- frequencies: prefixes of `(1.00, 1.37, 1.73, 2.11)`
- local perturbation strength: `0.04 / sqrt(mode_count)`
- nearest-neighbor stress coupling: `0.02 * sqrt(omega_i omega_{i+1}) X_i X_{i+1}`
- modular parameters: `s in {-0.25,-0.125,0,0.125,0.25}`
- clock refinement: `T/beta in {2,4}`, `eta in {0.125,0.0625}`

## Preregistered gates

All must pass across every frozen mode count:

- faithful density support;
- density trace error `<= 1e-12`;
- finite cocycle/unitarity/chain/transport/modular-group residuals `<= 1e-10`;
- uncoupled tensor-factorization residual `<= 1e-8`;
- coupled nonfactorization residual `>= 1e-4`;
- physical modular mismatch `>= 1e-4`;
- regulated readout mismatch `>= 1e-5`;
- cocycle readout-transport residual `<= 1e-9`;
- eta-refinement relative change `<= 2e-2`;
- observable retention `>= 1e-4`.

These thresholds are frozen before the first CI result. A failure is preserved and is not repaired by changing scientific criteria.

## Scope boundary

A PASS establishes only bounded numerical/algebraic stability for the frozen 2–4 mode finite Type-I family. It is not a field-mode limit, not a Type-II/III classification, not a continuum Connes-cocycle result, and not evidence for continuum QFT or gravitational dynamics.

The continuum status remains:

`BLOCKED_NOT_ESTABLISHED_BY_FINITE_MATRICES`

## Reproduce

```bash
python -m pip install -r candidates/multi-mode-cocycle-regulator/requirements.txt
python candidates/multi-mode-cocycle-regulator/multi_mode_scan.py --strict --output multi-mode.json
python -m unittest discover -s candidates/multi-mode-cocycle-regulator -p 'test_*.py' -v
```

© 2026 Robert Frost
