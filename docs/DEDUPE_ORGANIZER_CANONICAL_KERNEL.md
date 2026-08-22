# Dedupe/Organizer Canonical Kernel v1

## Purpose

This kernel turns the project's strongest recurring ideas into enforceable repository rules rather than another narrative summary.

The architecture is based on one universal immutable object envelope, typed payloads, and first-class relationship/provenance edges. Domain-specific projections—search indexes, dashboards, embeddings, summaries, graphs, rankings—are rebuildable views and never authoritative state.

## Canonical flow

`observe/acquire -> immutable object -> provenance edge -> classify/evaluate -> canonicalize -> project -> alert/report`

Mutation is deliberately outside this flow. Detection/evaluation may run autonomously; destructive or state-changing remediation belongs to a separate authorized, bounded, reversible transaction path.

## Core invariants

1. **No information-bearing transformation without provenance.** Any derived object must name at least one provenance event that identifies its inputs and transformation.
2. **Raw records are immutable.** A stable object identifier must not silently acquire different content.
3. **Duplicate detection is not deletion authority.** Canonicalization may select a canonical representative, merge metadata, quarantine, retain, reject from a projection, or defer; it does not imply physical deletion.
4. **Projections are not authoritative.** A projection must declare `authority_class=PROJECTION` and `authoritative=false`.
5. **Reconstruction is not originality.** Reconstructed objects must remain labeled reconstructed and linked to their source material and assumptions.
6. **Evidence is not semantic truth.** A signature/hash can establish integrity/provenance of a record; it does not prove the semantic truth of a claim.
7. **Unknown stays unknown outside the provenance graph.** Absence of a provenance path is not permission to infer one.
8. **Software PASS is scoped.** CI/test success establishes software/test qualification only, not empirical, scientific, forensic, or semantic truth unless a distinct validation explicitly establishes that domain claim.
9. **Detectors and mutators are separate trust domains.** Detection may observe, score, journal, alert, and prove; mutation requires authorization and a reversible transaction record.
10. **Bounded Android execution.** Device-local workers must be resource-bounded, restart-safe, idempotent, checkpointed, and must not substitute host evidence for authentic device-origin evidence.
11. **Mistake learning is append-only.** Mistake/event history is immutable authority; registries and dashboards are rebuildable projections.
12. **Mechanical guards must actually be in the execution path.** Semantic heuristics are review aids, not fake deterministic enforcement.

## Foundational object classes

The implementation should prioritize a small stable kernel rather than instantiate every possible schema immediately:

- PROJECT
- GOAL
- CONVERSATION
- MESSAGE
- FILE
- BLOB
- ARTIFACT
- SOURCE
- PROVENANCE_EVENT
- FILTER_DECISION
- DUPLICATE_GROUP
- CLAIM
- EVIDENCE
- DECISION
- STRATEGY
- EXECUTION
- VALIDATION
- MISSING_ARTIFACT
- RECONSTRUCTION
- MANIFEST

Everything else can extend the same envelope without changing the storage architecture.

## Universal object envelope

Required semantic fields:

- `object_id`: stable identifier
- `schema_version`: envelope version
- `type`: typed payload discriminator
- `content_hash`: immutable content digest
- `identity_hash`: logical identity digest when distinct from content
- `created_at`, `ingested_at`, optional observation/source timestamps
- `status`: lifecycle/canonical state
- `epistemic_status`: observed/derived/inference/etc.
- `verification_status`: validation state
- `confidence`: calibrated 0..1 value
- `authority_class`: AUTHORITATIVE_RECORD, DERIVED_RECORD, or PROJECTION
- `authoritative`: boolean, mechanically constrained by authority class
- `provenance_ids`: provenance-event references
- `payload`: typed domain content
- `extensions`: non-authoritative extension namespace unless separately governed

## Canonicalization semantics

Canonicalization is an identity and relationship decision, not a deletion decision.

Supported filter decisions are:

- RETAIN
- REJECT_FROM_PROJECTION
- MERGE
- QUARANTINE
- DEFER
- PROMOTE

Physical deletion is intentionally absent from this vocabulary. If the larger system ever performs deletion, it must be a separate mutation transaction with explicit authorization, evidence preservation, reversibility/backup policy, and audit provenance.

## Claim/evidence discipline

Claims must distinguish:

- OBSERVED
- REPORTED
- DERIVED
- INFERENCE
- SPECULATION
- PREDICTION
- UNKNOWN

Verification status is separate from epistemic status. A derived claim can be reproducibly derived while still being scientifically or semantically unverified.

A VERIFIED claim must reference evidence. Evidence objects may support or contradict claims and must record provenance and integrity state.

## Provenance model

A provenance event records:

- input object IDs
- operation
- tool and version
- rule/model identifier if any
- parameters
- output object IDs
- timestamp
- operator/worker
- deterministic flag

The key invariant is edge completeness: an information-bearing derived object cannot exist canonically without an edge explaining where it came from.

## Guardian/Sentinel integration

Guardian and Sentinel should be projections/consumers of this same canonical state model rather than separate epistemic systems.

Guardian's read-only/detection side may:

- inventory
- hash
- compare baselines
- score
- journal
- alert
- generate manifests

Its mutation side must remain a separate authorized transaction boundary using copy/verify/remove style reversible operations where possible.

## Mistake Prevention integration

Mistake events are append-only evidence records. Causal classes, dashboards, and registries are projections. Deterministic guards apply only when a structured predicate is actually interceptable; ambiguity, attribution, scope inflation, and source insufficiency remain semantic review problems. Provenance taint may propagate only over explicit edges and returns UNKNOWN outside the graph.

## Automation policy

The autonomous controller should select the highest-value unblocked work item, but promotion gates must be evidence-based. Missing source material blocks claims that depend on it; it does not justify choosing a convenient value. Failed tests block success claims. Missing physical evidence blocks device-validation claims.

## Release criteria for the kernel

A kernel release is qualified when:

1. schemas parse;
2. valid fixture passes;
3. derived object without provenance fails;
4. projection claiming authority fails;
5. VERIFIED claim without evidence fails;
6. DELETE-style dedupe decision fails;
7. reconstructed-as-original fixture fails;
8. same object ID with different content hash fails;
9. provenance references resolve;
10. all tests pass under the repository's supported Python runtime.

This qualifies the kernel mechanics only. It does not establish correctness of downstream scientific, forensic, or security conclusions.
