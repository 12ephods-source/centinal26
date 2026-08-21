# Continuity proposal adapter

Status: CANDIDATE / HOST-QUALIFICATION REQUIRED

`frost_core.continuity_proposal.ContinuityProposalAdapter` is the first implementation allowed by the canonical Second Brain authority map. It converts historical AICCEP/Second Brain continuity records into one immutable, content-addressed **proposal object**.

It does not create a parallel runtime or database authority.

## Authority boundary

Canonical machine continuation remains:

`automation/PROJECT_STATE.json`

Historical AICCEP-OS and AI-First Second Brain records are migration/provenance/domain-semantics sources only. The adapter does not mutate the machine continuation file, advance aliases/current pointers, authorize execution, resolve contradictions, or promote epistemic state.

## Generic input contract

An export contains:

- `source_system`
- `export_version`
- `entities[]` with source identity, entity type, optional epistemic status, optional revision parent, and payload
- `relationships[]` whose endpoints must exist in the same export
- `artifacts[]` with exact lowercase SHA-256 identities

The adapter canonicalizes entity and relationship order so semantically identical reordered exports produce the same proposal identity.

## Direct AI-First Second Brain v0.2 bridge

`frost_core.second_brain_context.SecondBrainContextAdapter` consumes the historical v0.2.0 `export-context` shape directly. The historical exporter produces:

- one `project` object;
- project-scoped `decisions`, `experiments`, `findings`, `security_cases`, `tasks`, `code_modules`, `test_plans`, and `library` collections;
- `runs` associated with exported experiments;
- typed `links`;
- `schema_version = 0.2.0` and a generated timestamp.

The bridge also accepts optional richer collections (`theory`, `evidence`, `environments`, `ai_sessions`, `workbench`, and `revisions`) so a future lossless exporter can provide them without changing the generic proposal schema.

Every historical record is preserved inside the proposal payload together with an exact canonical-JSON SHA-256. Second Brain IDs are preserved as source IDs. Epistemic status and `provenance_json` remain part of the source record. Typed link endpoint metadata is retained when present.

The generated timestamp is deliberately excluded from the normalized proposal identity: re-exporting unchanged records at a later time is idempotent.

Second Brain `library.checksum_sha256` values become artifact identities. If bytes are supplied during qualification they are independently re-hashed. If bytes are unavailable, the hash is preserved without claiming byte verification.

A v0.2 link whose endpoint was omitted from the context packet fails closed. The bridge does not invent the missing Theory, Evidence, Run, or other record merely to make migration succeed.

## Validation and failure semantics

The complete export is validated before storage. Invalid duplicate identities, revision references, relationship endpoints, artifact hashes, or supplied-byte hash mismatches fail before any proposal object is written.

A successful ingest performs one content-addressed `CanonicalObjectStore.put`. Re-ingesting identical content is idempotent.

Artifact bytes are not duplicated. When bytes are explicitly supplied to the adapter for qualification, their SHA-256 is recomputed and must match the historical artifact reference. When bytes are unavailable, the historical hash is preserved with `HASH_PRESERVED_BYTES_NOT_PROVIDED`; this is provenance preservation, not byte verification.

## Deliberately absent capabilities

The adapter has no API for:

- execution;
- capability authorization;
- alias/current-pointer mutation;
- automatic contradiction resolution;
- automatic epistemic promotion;
- rewriting the historical AICCEP database;
- storing duplicate artifact bytes.

## Promotion gate

Host qualification requires at minimum:

1. deterministic stable identity mapping;
2. duplicate-ingest idempotency;
3. relationship and typed-link preservation;
4. revision-lineage validation;
5. epistemic-state preservation;
6. SHA-256 preservation and supplied-byte verification;
7. failed validation leaves no proposal object;
8. no alias/current-pointer side effect;
9. no execution authority;
10. direct compatibility with the historical Second Brain v0.2.0 context export;
11. repository CI and Automation gates PASS on the exact candidate head.

Physical Android/Termux validation remains a separate release gate and is not affected by this adapter.
