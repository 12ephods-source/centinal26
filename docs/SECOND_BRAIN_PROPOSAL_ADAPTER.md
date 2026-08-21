# Second Brain proposal-only migration adapter

Status: CANDIDATE

Authority source: `automation/SECOND_BRAIN_AUTHORITY.json`.

## Purpose

`centinal26.second_brain_adapter` converts historical AI-First Second Brain v0.2.0 project context exports into deterministic, provenance-preserving **proposals** for the canonical Centinal26 continuity path.

It does not write the historical Second Brain database, AICCEP database, canonical event store, artifact store, task queue, or execution plane.

## Source contract

The adapter is grounded in the v0.2.0 `export-context` structure. The historical exporter emits:

- `generated_utc`
- `schema_version`
- one `project` object
- project-scoped `decisions`, `experiments`, `findings`, `security_cases`, `tasks`, `code_modules`, `test_plans`, and `library`
- `runs` associated with exported experiments
- typed `links` whose endpoints are among linked exported IDs when present

The adapter also accepts optional richer collections (`theory`, `evidence`, `environments`, `ai_sessions`, `workbench`, `revisions`) so a future lossless historical exporter can supply them without changing the proposal schema.

## Proposal semantics

For every source record the adapter preserves:

- original immutable source ID
- exact canonical-JSON record hash
- source record body
- epistemic status
- parsed provenance metadata when available
- project association
- entity type

The deterministic proposal identity is derived from:

`source system + entity type + source ID`

The source-record SHA-256 is stored separately. Therefore a repeated identical record is idempotent, while changed content under the same stable identity is an explicit conflict.

## Relationships

Second Brain `links` become relationship proposals. Missing endpoints are never guessed or repaired.

Default behavior records them as `UNRESOLVED_EXTERNAL`. Strict mode fails closed if either endpoint is absent from the export.

## Artifact integrity

Historical `library` records become artifact proposals. Their declared SHA-256 is preserved.

If the caller provides an independently observed SHA-256 for that source artifact, it must match the declared digest or conversion fails closed. When the bytes are unavailable, the proposal remains `DECLARED_UNVERIFIED`; the adapter does not fabricate verification.

## Idempotency and atomic conflict behavior

`ProposalIndex` is an in-memory qualification model, not a persistence layer. It demonstrates the contract a future authorized canonical writer must preserve:

- repeated identical proposal IDs with identical immutable hashes are duplicates;
- repeated proposal IDs with different immutable hashes are conflicts;
- relationship replays behave the same way;
- a conflict does not partially mutate the index.

## Explicit non-authority

All proposal bundles and records contain:

- `authority = proposal_only`
- `execution_authorized = false`
- `truth_promoted = false`

The adapter cannot:

- authorize an objective;
- create an execution grant;
- convert knowledge tasks into executable tasks;
- resolve contradictions;
- promote epistemic status;
- create canonical artifact bytes;
- silently rewrite AICCEP or Second Brain;
- promote host evidence to physical-device evidence.

## Qualification gate

The tests cover:

1. actual v0.2 context-export shape;
2. deterministic conversion;
3. source-ID, epistemic-status, and provenance preservation;
4. experiment/run relation preservation;
5. explicit unresolved relationships;
6. strict missing-endpoint rejection;
7. independent artifact-hash match;
8. unavailable-artifact non-promotion;
9. artifact mismatch rejection;
10. duplicate-ingest idempotency;
11. changed-content conflict atomicity;
12. proposal-bundle tamper detection;
13. optional theory/evidence/revision preservation;
14. duplicate source identity rejection;
15. source export immutability.

A later canonical writer may consume these proposals only after the ordinary Centinal26 authorization, governance, validation, provenance, and promotion rules are applied.