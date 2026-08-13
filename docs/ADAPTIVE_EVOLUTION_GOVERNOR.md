# Adaptive Evolution Governor

Status: **DRAFT-CANONICAL**

This document is an implementation companion to the Dragon Evolution horizon definition. It does not replace the horizon document or promote it to CANONICAL.

## Component boundary

`AutomationMetaPolicy` remains the constitutional authority envelope. The Adaptive Evolution Governor is subordinate: it may derive stricter capability-specific limits, but it may not loosen MetaPolicy, expand authority, permit external side effects, or self-modify the governing policy.

`AutomationMetaPolicy -> Adaptive Evolution Governor -> AutomationEvolutionEnvelope -> Candidate Experiment -> Constitutional Gate -> Evolution Decision`

## Capability-specific differential plasticity

The mutation budget is capability-indexed:

`mu(c,t) = mu_min(c) + [mu_max(c)-mu_min(c)] * exp(-k*M(c,t)) * [eta + (1-eta)*U(c,t)]`

`M(c,t)` is capability maturity and `U(c,t)` is unresolved uncertainty/opportunity. A mature core capability and a frontier capability can therefore have different mutation budgets at the same time.

### Initial maturity composition

All components are normalized to `[0,1]`:

- validation stability: 0.20
- evidence confidence: 0.15
- rollback readiness: 0.15
- environment coverage: 0.15
- repeated successful use: 0.10
- promotion-test closure: 0.10
- generalization: 0.15

This composition is deliberately conservative. Strong one-host results cannot dominate missing generalization or environment coverage.

Initial uncertainty composition:

- missing environment coverage: 0.40
- missing generalization: 0.30
- missing repeated success: 0.20
- unresolved promotion closure: 0.10

These weights are calibration parameters, not empirical constants. They require later holdout testing.

## Constitutional pre-gate

Live candidate evidence showed that `HardValid` cannot be a Boolean. Missing required evidence is not equivalent to a failed mutation.

The pre-gate therefore distinguishes:

- `PASS`
- `BLOCKED_PENDING_VALIDATION`
- `BLOCKED_INSUFFICIENT_EVIDENCE`
- `BLOCKED_ROLLBACK_REQUIRED`
- `HUMAN_REVIEW_REQUIRED`
- `REJECT_VALIDATION_FAILED`

Only `PASS` enters the four-way evolutionary decision. An explicit deterministic `FAIL` may be rejected. Missing deterministic validation is preserved as a blocked state.

## Four-way evolutionary decision

After the constitutional gate passes:

1. `PROMOTION_CANDIDATE`: compatible with the parent form and current-environment Fit exceeds the promotion threshold.
2. `POLYMORPH_CANDIDATE`: persistent niche advantage, compatible with the parent, and cheaply selectable.
3. `SPECIATION_CANDIDATE`: persistent niche advantage that is useful but incompatible with the parent form.
4. `HOLD`: valid evidence exists but promotion, polymorphism, and speciation thresholds are not yet satisfied.

An explicit deterministic validation failure is a separate `REJECT` outcome.

## Live seed: APB-CAP-0004

The first `AutomationEvolutionEnvelope` was seeded from the live Frost Evolution Fabric capability `APB-CAP-0004` under `meta-automation-v1`.

Evidence inputs used for generation 0:

- validation stage: `HOST_VALIDATED`
- capability confidence: `0.99`
- rollback available in the real host concurrency experiment
- environment evidence: one worker/platform
- prior v1.4 generalization result: `FAIL`
- v1.6 real host concurrency result: mean speedup `2.8927416119594094`, mean wall reduction `0.6529861601078487`
- physical-device validation: pending
- next promotion test requires at least 3 workers and 2 platforms with holdout validation

Conservative normalized components:

- validation stability = 0.70
- confidence = 0.99
- rollback readiness = 1.00
- environment coverage = 0.25
- repeated success = 0.25
- promotion closure = 0.25
- generalization = 0.00

Result:

- `M(c,t) = 0.526`
- `U(c,t) = 0.825`
- `mu_min = 0.02`
- `mu_max = 0.20`
- `k = 2.0`
- `eta = 0.10`
- `mu(c,t) = 0.072962`

Initial envelope constraints:

- confidence floor: `0.93`
- occurrence floor: `3`
- maximum autonomous risk: `LOW`
- independent validated evidence depth: `3`
- promotion delta minimum: `0.05`
- branch delta minimum: `0.10`
- persistent niche occurrence minimum: `3`
- persistent niche duration minimum: `P14D`
- persistent niche replication minimum: `2`

Protected zero-regression dimensions are semantic equivalence, failure count, authority scope, and rollback readiness.

## Real candidate exercise: APB-EXP-0002

The real host concurrency candidate has:

- ten paired trials
- LOW experiment risk
- confidence `0.98`
- rollback defined
- semantic equivalence in every trial
- zero failures
- mean wall reduction `0.6529861601078487`
- only one independently validated experiment/environment scope

No linked `AutomationValidation.deterministic_status=PASS` was found for this candidate at bootstrap time.

Therefore the live candidate currently resolves to:

`BLOCKED_PENDING_VALIDATION`

and does **not** enter the four-way decision.

Even if an explicit deterministic PASS is later supplied, the current generation-0 envelope requires independent evidence depth `3`; the candidate currently has depth `1`, so it would next resolve to `BLOCKED_INSUFFICIENT_EVIDENCE` until additional independent validation exists.

This is intentional fail-closed behavior. The governor must not manufacture a PASS merely to satisfy a canonical-promotion criterion.

## Promotion state

Dragon Evolution remains **DRAFT-CANONICAL**.

Promotion gates:

1. At least one live `AutomationEvolutionEnvelope` seeded from an `APBCapability`: **PASS** (`APB-CAP-0004`, generation 0).
2. `M(c,t)` composition specified and tested: **IMPLEMENTED; CI validation pending for this change set**.
3. Conservative initial calibration parameters established: **PASS as initial policy values; empirical calibration remains future work**.
4. Four-way decision exercised against a real candidate after constitutional pre-gate PASS: **OPEN**. `APB-EXP-0002` is currently blocked first by missing deterministic PASS and then by insufficient independent evidence depth.

Do not promote to CANONICAL by weakening gate 4.
