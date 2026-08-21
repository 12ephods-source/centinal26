# AI-First Second Brain canonical authority map

Status: CANDIDATE

This document defines where useful semantics from **AI-First Second Brain v0.2.0** and historical **AICCEP-OS v1.1.0** belong inside the current Automation OS architecture. The purpose is convergence: one machine continuation authority, one bounded execution plane, one artifact-identity authority, and proposal-only migration from historical stores.

Machine-readable authority: `automation/SECOND_BRAIN_AUTHORITY.json`.

## Canonical decision

Do **not** evolve either Second Brain or the historical AICCEP database into another live canonical runtime.

The repository already declares `automation/PROJECT_STATE.json` as the machine continuation authority. That declaration is binding for this integration. AICCEP and Second Brain contribute domain semantics, historical records, schema ideas, relationships, revisions, and migration/provenance inputs; they do not remain parallel authoritative databases after convergence.

| State category | Canonical authority |
| --- | --- |
| Repository/release governance | Centinal26 `main` |
| Machine project continuation | `automation/PROJECT_STATE.json` |
| Automation control plane | `automation/` in Centinal26 |
| Canonical knowledge/project metadata | Centinal26 canonical continuity layer |
| Historical continuity semantics / migration source | AICCEP-OS v1.1.0 lineage |
| Second Brain v0.2.0 | Domain semantics and migration source only |
| Artifact identity/immutable bytes/atomic staging | Frost CORE / canonical shared runtime |
| Bounded execution and independent verification | Centinal26 + Frost CORE |
| Research-agent application behavior | AAARD |

The historical AICCEP database must not be silently rewritten. Preserving it as immutable migration/provenance input is different from treating it as a second live canonical state store.

## Why this correction matters

The project already has a canonical machine continuation record. Assigning live project/knowledge authority to a separate AICCEP database would reintroduce the exact ambiguity this integration is intended to remove:

- Which project record wins a conflict?
- Which revision is current?
- Which backup restores canonical state?
- Which audit history governs promotion?
- Which task state may drive execution?

The answer after convergence must be singular: canonical decisions are represented through the Centinal26 continuity/governance path; historical AICCEP and Second Brain data enter only through provenance-preserving proposals.

## Roadmap ranks 10–18

The machine-readable map classifies each item as `CANONICAL_ALREADY`, `PARTIAL`, or `NEW_REQUIRED`.

- Content-addressed artifact storage is **reuse**, not greenfield work.
- Encrypted/off-device disaster recovery remains a genuine gap in the canonical continuity path.
- Signed portable interchange is partial and should be unified under Centinal26 governance.
- Multiwriter knowledge concurrency remains a genuine gap.
- Relation integrity and manifest semantics need hardening, not parallel implementations.
- JSON-schema governance and single-source schema generation belong under Centinal26 governance.
- Orphan detection belongs in canonical continuity and must be non-destructive before any garbage collection is authorized.

## Entity mapping

Second Brain/AICCEP entities map into canonical state rather than becoming another database authority.

Examples:

- `Experiment` and `Run` metadata map into canonical continuity; execution remains Centinal26/Frost CORE; immutable outputs remain Frost CORE.
- `Evidence` metadata and relationships map into canonical continuity; evidence bytes remain Frost CORE.
- `Artifact` metadata maps into canonical continuity; artifact identity and immutable bytes remain Frost CORE.
- `Code Module` metadata maps into canonical continuity; source revisions remain Git.
- Knowledge tasks map into canonical continuity; executable tasks remain in the bounded execution plane.

The metadata/bytes split is intentional, but it does not imply multiple governance authorities.

## First adapter boundary

The first integration adapter must be one-way and proposal-only:

`Second Brain/AICCEP record -> validate -> map stable identity -> verify artifact hashes -> preserve provenance/revision/epistemic state -> emit canonical proposal`

It must be idempotent. Re-ingesting identical source records must not produce duplicate canonical objects.

The adapter may not:

- rewrite the historical AICCEP database silently;
- keep AICCEP as a parallel live canonical database;
- create another artifact byte store;
- create another execution runtime;
- resolve contradictions automatically;
- promote epistemic state automatically;
- convert prose into arbitrary shell execution;
- grant execution authority.

## Differential qualification gate

Before any historical Second Brain/AICCEP runtime is superseded operationally, representative source data must demonstrate:

1. stable or deterministic identity mapping;
2. relationship preservation;
3. revision lineage preservation;
4. epistemic-state preservation;
5. artifact SHA-256 preservation;
6. experiment/run linkage preservation;
7. duplicate-ingest idempotency;
8. failure atomicity;
9. deterministic export of resulting canonical state;
10. exactly one machine continuation authority.

Physical Android/Termux validation remains a separate gate. Host integration success cannot promote `DEVICE_VALIDATED` or `PERSISTENT_VALIDATED`.

## Next implementation

After this authority map qualifies, the next change should be the smallest read-only/proposal-only adapter satisfying this contract. It should consume Second Brain/AICCEP exports or SQLite state without granting either historical store write or execution authority.

Only after differential/idempotency tests pass should genuinely missing roadmap capabilities be implemented.
