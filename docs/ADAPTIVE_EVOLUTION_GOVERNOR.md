# Adaptive Evolution Governor

Status: **DRAFT-CANONICAL**

This document is an implementation companion to the Dragon Evolution horizon definition. It does not replace the horizon definition or promote Dragon Evolution to CANONICAL.

## Component boundary

`AutomationMetaPolicy` remains the constitutional authority envelope. The Adaptive Evolution Governor is subordinate: it may derive stricter capability-specific limits, but it may not loosen MetaPolicy, expand authority, permit disallowed side effects, or self-modify the governing policy.

`AutomationMetaPolicy -> Adaptive Evolution Governor -> AutomationEvolutionEnvelope -> Candidate Experiment -> Constitutional Gate -> Evolution Decision`

The Governor carries constraints, not promotion authority.

## Capability-specific differential plasticity

The mutation budget is capability-indexed:

`mu(c,t) = mu_min(c) + [mu_max(c)-mu_min(c)] * exp(-k*M(c,t)) * [eta + (1-eta)*U(c,t)]`

`M(c,t)` is capability maturity and `U(c,t)` is unresolved uncertainty/opportunity. Two capabilities at the same time may therefore have materially different mutation budgets.

### Initial maturity composition

All components are normalized to `[0,1]` and are evidence-derived rather than age-derived:

- validation stability: weight `0.25`
- regression resilience: weight `0.20`
- environment coverage: weight `0.15`
- rollback readiness: weight `0.15`
- repeated successful use: weight `0.15`
- promotion-test closure: weight `0.10`

Initial uncertainty composition:

- evidence gap: weight `0.35`
- environment gap: weight `0.30`
- model error: weight `0.20`
- frontier opportunity: weight `0.15`

These weights and normalized input values are conservative calibration parameters, not empirical constants. They require later holdout testing.

## Constitutional pre-gate / HardValid

`HardValid` is computed from a typed constitutional gate so missing evidence is not collapsed into the same reason as an explicit failed mutation.

Gate dispositions are:

- `PASS`
- `BLOCKED_UNAUTHORIZED`
- `BLOCKED_PENDING_VALIDATION`
- `BLOCKED_INSUFFICIENT_EVIDENCE`
- `BLOCKED_ROLLBACK_REQUIRED`
- `HUMAN_REVIEW_REQUIRED`
- `REJECT_VALIDATION_FAILED`

Only `PASS` yields `HardValid=true` and permits evaluation of compatibility and fitness. Missing deterministic validation remains preserved as a blocked state. An explicit deterministic `FAIL` remains distinguishable in evidence.

MetaPolicy constraints include authorization, deterministic validation when required, rollback, confidence, occurrence count, evidence depth, risk, schema-mutation authority, and external-side-effect authority.

## Compatibility and Fit

For protected metric `j`:

`Delta_j(x,F,e) = S_j(x,e) - S_j(F,e)`

Compatibility requires all protected metrics to remain within their allowed regression tolerances after the constitutional gate has passed:

`Compatible(x,F) iff HardValid(x) and for every protected j: Delta_j >= -tau_j`

Environment-specific fitness is computed independently:

`Fit(x,e) = sum_j w_j(e) * Delta_j(x,F,e)`

A high Fit score cannot override `HardValid=false`.

## Persistent niches

A niche becomes persistent only after it clears recurrence, duration, independent replication, and validated-advantage thresholds. One successful niche experiment cannot create a lineage.

The initial generation-0 persistence floors are:

- independent niche occurrences: `3`
- duration: `P14D`
- independent successful replications: `2`
- median niche advantage: at least the branch delta threshold

## Four-way evolutionary decision

After the constitutional gate passes:

1. `PROMOTION_CANDIDATE`: compatible with the parent form and current-environment Fit exceeds the promotion threshold.
2. `POLYMORPH_CANDIDATE`: persistent niche advantage, compatible with the parent, and low switching cost.
3. `SPECIATION_CANDIDATE`: persistent niche advantage, incompatible with the parent, and high coexistence cost.
4. `REJECT_FROM_PROMOTION`: the candidate is blocked, invalid, or has not cleared promotion/polymorphism/speciation thresholds. Evidence is preserved and the gate reason distinguishes the cause.

Speciation therefore requires more than useful incompatibility: it also requires a persistent niche and evidence that coexistence inside the parent form is materially costly.

## Live seed: APB-CAP-0004

The sole active generation-0 `AutomationEvolutionEnvelope` is seeded from the live Frost Evolution Fabric capability `APB-CAP-0004` under `meta-automation-v1`.

A second generation-0 seed was observed during implementation and was explicitly marked `superseded`; single-active-lineage selection is now fail-closed in code.

Evidence context includes:

- validation stage: `HOST_VALIDATED`
- capability confidence: `0.99`
- rollback available in the real host concurrency experiment
- environment evidence limited to one worker/platform
- prior generalization failure preserved
- v1.6 real host concurrency result: mean speedup `2.8927416119594094`, mean wall reduction `0.6529861601078487`
- physical-device validation pending
- next promotion test requires broader workers/platforms and holdout validation

Conservative normalized maturity inputs for the active seed:

- validation stability = `0.75`
- regression resilience = `0.70`
- environment coverage = `0.25`
- rollback readiness = `1.00`
- repeated success = `0.50`
- promotion closure = `0.25`

This produces:

- `M(c,t) = 0.615`

Conservative uncertainty inputs:

- evidence gap = `0.50`
- environment gap = `0.75`
- model error = `0.10`
- frontier opportunity = `0.23333333333333334`

This produces:

- `U(c,t) = 0.455`

With:

- `mu_min = 0.01`
- `mu_max = 0.20`
- `k = 2.0`
- `eta = 0.10`

The resulting mutation budget is:

- `mu(c,t) = 0.038295383`

Initial envelope constraints:

- confidence floor: `0.93`
- occurrence floor: `3`
- maximum autonomous risk: `LOW`
- independent validated evidence depth: `3`
- promotion delta minimum: `0.05`
- branch delta minimum: `0.15`
- persistent niche occurrence minimum: `3`
- persistent niche duration minimum: `P14D`
- persistent niche replication minimum: `2`

Protected zero-regression dimensions are semantic equivalence, failure count, and rollback availability.

## Real candidate exercise: APB-EXP-0002

The stored real host-concurrency candidate has:

- ten paired trials
- LOW experiment risk
- confidence `0.98`
- rollback defined
- semantic equivalence in every trial
- zero failures
- mean wall reduction `0.6529861601078487`
- model error of `9.317254513433963` percentage points relative to prior modeled replay
- only one independently validated experiment/environment scope

Using the provisional current-environment Fit weights from the dry run produced:

`Fit(x,e) = 0.41978237681338465`

No linked independent `AutomationValidation.deterministic_status=PASS` was found for this candidate at the dry-run point.

Therefore the candidate resolves first to:

`BLOCKED_PENDING_VALIDATION -> REJECT_FROM_PROMOTION`

The positive fitness evidence remains preserved. It does not override the constitutional gate.

Even if an explicit deterministic PASS is later supplied, the active generation-0 envelope requires evidence depth `3`; the candidate currently has depth `1`, so it would next resolve to `BLOCKED_INSUFFICIENT_EVIDENCE` until additional independent validation exists.

## Centinal26 integration

`evolution.evaluate_candidate` is registered as a host-safe advisory capability through the existing Centinal26 path:

`Grant -> durable queue -> bounded executor -> deterministic recomputation verifier -> hash-linked audit`

The adapter returns `promotion_authority=false`. It can classify evidence; it cannot promote a candidate, widen authorization, mutate MetaPolicy, or certify physical-device execution.

## Promotion state

Dragon Evolution remains **DRAFT-CANONICAL**.

Promotion gates:

1. At least one live `AutomationEvolutionEnvelope` seeded from an `APBCapability`: **PASS** (`APB-CAP-0004`, generation 0; exactly one active envelope).
2. `M(c,t)` composition specified and tested: **IMPLEMENTED; repository CI validation pending for this change set**.
3. Conservative initial calibration parameters established: **PASS as provisional policy values; empirical calibration remains open**.
4. Four-way decision exercised against a real candidate after constitutional pre-gate PASS: **OPEN**. `APB-EXP-0002` is a real dry-run input, but it correctly stops before compatibility/branch classification because required deterministic validation and evidence depth are incomplete.

Do not promote to CANONICAL by weakening Gate 4. The next empirical milestone is an independently deterministically validated real candidate with sufficient evidence depth, followed by a full compatible/fitness/persistence classification under the same immutable MetaPolicy envelope.
