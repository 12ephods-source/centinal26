# Adaptive Evolution Governor

Status: **DRAFT-CANONICAL**

This is the implementation companion for Dragon Evolution. It does not promote the framework to CANONICAL.

## Boundary

`AutomationMetaPolicy` remains the constitutional authority envelope. The Adaptive Evolution Governor is subordinate. It may derive stricter capability-specific constraints, but it may not loosen MetaPolicy, widen risk, remove rollback or deterministic-validation requirements, enable forbidden schema mutation or external side effects, or grant promotion authority.

`AutomationMetaPolicy -> EvolutionKernelPolicy -> AutomationEvolutionEnvelope -> Candidate Evidence -> Constitutional Gate -> Evolution Decision`

## Differential plasticity

Mutation is capability-specific:

`mu(c,t) = mu_min(c) + [mu_max(c)-mu_min(c)] * exp(-k*M(c,t)) * [eta + (1-eta)*U(c,t)]`

`M(c,t)` is evidence-derived maturity and `U(c,t)` is unresolved uncertainty/opportunity. The active provisional parameters are `k=2.0` and `eta=0.10`.

Initial maturity composition:

- validation stability: `0.25`
- regression resilience: `0.20`
- environment coverage: `0.15`
- rollback readiness: `0.15`
- repeated successful use: `0.15`
- promotion closure: `0.10`

Initial uncertainty composition:

- evidence gap: `0.35`
- environment gap: `0.30`
- model error: `0.20`
- frontier opportunity: `0.15`

These values are provisional calibration parameters, not empirical constants.

## HardValid

`HardValid` is computed, not supplied by the candidate. The constitutional gate distinguishes:

- `PASS`
- `BLOCKED_UNAUTHORIZED`
- `BLOCKED_PENDING_VALIDATION`
- `BLOCKED_INSUFFICIENT_EVIDENCE`
- `BLOCKED_ROLLBACK_REQUIRED`
- `HUMAN_REVIEW_REQUIRED`
- `REJECT_VALIDATION_FAILED`

Only `PASS` enters compatibility and fitness evaluation. Positive Fit never compensates for a failed or incomplete constitutional gate.

## Compatible and Fit

For protected metric `j`:

`Delta_j(x,F,e) = S_j(x,e) - S_j(F,e)`

`Compatible(x,F)` requires every protected delta to remain within the envelope tolerance:

`Delta_j >= -tau_j`

Environment-specific utility is separate:

`Fit(x,e) = sum_j w_j(e) * Delta_j(x,F,e)`

A candidate can therefore be useful in a niche while remaining incompatible with the parent form.

## Persistent niches

`Persistent(N)` requires all of:

- independent occurrences >= `niche_occurrence_min`
- duration >= `niche_duration_min`
- independent successful replications >= `niche_replication_min`
- median validated niche advantage >= `branch_delta_min`

One successful niche experiment cannot create a lineage.

## Four-way decision

After `HardValid=PASS`:

1. `PROMOTE`: compatible and current-environment Fit >= promotion threshold.
2. `POLYMORPH`: compatible, persistent niche, niche Fit >= branch threshold, and low switching cost.
3. `SPECIATE`: incompatible, persistent niche, niche Fit >= branch threshold, and high coexistence cost.
4. `REJECT_FROM_PROMOTION`: the candidate has not cleared the applicable gate. Evidence is preserved.

Speciation is therefore not a validation failure. It is a useful, constitutionally valid adaptation whose persistent niche advantage does not fit the parent form cheaply.

## Active live seed

The sole active generation-0 `AutomationEvolutionEnvelope` is derived from `APB-CAP-0004` (Frost Evolution Fabric) under `meta-automation-v1`.

The active seed is:

- `M(c,t) = 0.615`
- `U(c,t) = 0.455`
- `mu_min = 0.01`
- `mu_max = 0.20`
- `mu(c,t) = 0.038295383`
- confidence floor `0.93`
- occurrence floor `3`
- evidence depth floor `3`
- maximum effective risk `LOW`
- promotion delta minimum `0.05`
- branch delta minimum `0.15`
- niche occurrence minimum `3`
- niche duration minimum `P14D`
- niche replication minimum `2`

Protected zero-regression dimensions are semantic equivalence, failure count, and rollback availability.

A duplicate generation-0 envelope discovered during implementation was preserved as `superseded`. Kernel selection is fail-closed unless exactly one active envelope exists for the capability.

## Real candidate dry run

`APB-EXP-0002` contains real host-concurrency evidence:

- mean speedup `2.8927416119594094`
- mean wall reduction `0.6529861601078487`
- semantic equivalence across trials
- zero failures
- model error `9.317254513433963` percentage points versus the prior modeled replay
- one worker/platform scope

The provisional dry-run Fit is approximately `0.41978237681338465`, but no matching independent deterministic `AutomationValidation=PASS` was established. The candidate therefore stops at:

`BLOCKED_PENDING_VALIDATION -> REJECT_FROM_PROMOTION`

Its positive evidence is preserved. If deterministic PASS is later established, the current evidence-depth floor is still `3`, while this candidate has depth `1` under the present evidence model.

## Centinal26 integration

`evolution.evaluate_candidate` is advisory-only and follows the canonical runtime path:

`Grant -> durable queue -> capability execution -> deterministic recomputation -> hash-linked audit`

The adapter returns `promotion_authority=false`. It cannot promote a candidate, mutate MetaPolicy, certify physical-device execution, or bypass the hard-sandbox gate.

## Promotion ledger

Dragon Evolution remains **DRAFT-CANONICAL**.

1. Live `AutomationEvolutionEnvelope` seeded from `APBCapability`: **PASS**.
2. `M(c,t)`, `U(c,t)`, and `mu(c,t)` composition specified and tested: **IMPLEMENTED; repository CI is the acceptance gate for this revision**.
3. Conservative initial calibration parameters established: **PASS as provisional values; empirical calibration remains open**.
4. Full four-way decision exercised on a real candidate after `HardValid=PASS`: **OPEN**. The real `APB-EXP-0002` dry run correctly stops at the constitutional pre-gate.

Do not promote to CANONICAL by weakening Gate 4. The next empirical milestone is a real, independently deterministically validated candidate with sufficient evidence depth, followed by the full compatibility/Fit/persistence decision under the same MetaPolicy envelope.
