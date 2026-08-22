# Epistemic Integrity Protocol v1

## Objective

Maintain the strongest defensible current representation of each material claim without confusing lineage, cryptographic integrity, software execution, consensus, or repetition with truth.

The system is a **claim-promotion guard**, not a truth oracle.

## Core invariant

> No conclusion may be promoted beyond the strongest independent evidence supporting it.

This sits above the provenance invariant:

> No information-bearing transformation without a provenance edge.

The provenance rule protects history. The epistemic rule protects conclusions.

## Separate dimensions

Every material claim may carry independent states for:

- provenance
- integrity
- source semantics
- reproduction
- independent verification
- physical/device validation
- empirical validation
- scientific validation
- historical verification
- attribution

A PASS in one dimension never promotes another.

## Promotion ceiling

`scripts/epistemic_gate.py` computes only a maximum allowable epistemic label from recorded evidence. It does not determine whether the claim is absolutely true.

The ordered positive labels are:

`UNKNOWN < HYPOTHESIS < PLAUSIBLE < SUPPORTED < STRONGLY_SUPPORTED < ESTABLISHED_WITHIN_SCOPE`

`REJECTED` is separate and requires decisive verified counterevidence or an explicit failing domain gate.

Material unresolved contradictions cap positive promotion at `SUPPORTED`. A blocked or failing domain-specific gate caps a claim at `PLAUSIBLE`.

## Independence

Repeated copies, summaries, citations of the same upstream source, or multiple models repeating one source are one independence group. They do not count as independent corroboration.

## Scope

Every strong claim must carry a scope/version boundary. “0.4.0 passed tests in the build environment” is not equivalent to “0.4.0 is physically validated on Android.”

## Failure behavior

On missing evidence, return UNKNOWN/BLOCKED and continue to another READY claim. Never infer FALSE from missing evidence, and never infer absence from failure to observe.

## Automation

The controller should:

1. identify consequential claims whose evidence or dependencies changed;
2. rank by decision impact, falsification value, uncertainty reduction, accessibility, and cost;
3. inspect the highest-value READY claim;
4. validate source identity/integrity;
5. seek counterevidence and independent corroboration;
6. run deterministic checks where relevant;
7. apply this gate before changing the claim label;
8. preserve old states and the reason for any upgrade/downgrade;
9. notify only on material epistemic change or irreducible evidence boundary.
