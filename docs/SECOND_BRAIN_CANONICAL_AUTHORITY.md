# AI-First Second Brain canonical authority map

Status: CANDIDATE

This document defines where the useful semantics from **AI-First Second Brain v0.2.0** belong inside the current Automation OS architecture. It exists to prevent a new Second Brain release from creating a competing persistence, artifact, audit, or execution authority.

Machine-readable authority: `automation/SECOND_BRAIN_AUTHORITY.json`.

## Decision

Do **not** evolve the isolated Second Brain into another canonical runtime.

Use its strongest domain semantics—experiment/run separation, evidence and decision records, AI provenance, epistemic status, revisions, portable logical references, verified restore discipline, and artifact verification—as migration inputs to the existing canonical architecture.

The authority split is:

| State category | Canonical authority |
| --- | --- |
| Repository/release governance | Centinal26 `main` |
| Automation control plane | `automation/` in Centinal26 |
| Project continuity and knowledge metadata | AICCEP-OS v1.1.0 lineage |
| Artifact identity/immutable bytes/atomic staging | Frost CORE / canonical shared runtime |
| Bounded execution and independent verification | Centinal26 + Frost CORE |
| Research-agent application behavior | AAARD |
| Second Brain v0.2.0 | Domain semantics and migration source only |

This preserves the prior AICCEP rule that its historical v1.1.0 database cannot be silently rewritten by extension code. It also follows current Automation source-consolidation policy: reuse a verified bounded capability before rebuilding equivalent machinery.

## Why this is necessary

An isolated v0.3 implementation of roadmap ranks 10–18 would duplicate several facilities already present in current Automation history, especially content-addressed artifact storage, hashing, atomic writes, execution state, verification, and audit primitives.

The failure mode would be multiple plausible answers to questions such as:

- Which artifact registry is authoritative?
- Which project record wins a conflict?
- Which audit history governs promotion?
- Which revision is current?
- Which backup restores canonical state?
- Which executor is permitted to mutate state?

The authority map reduces those questions to one owner per state category.

## Roadmap ranks 10–18

The machine-readable map classifies each item as `CANONICAL_ALREADY`, `PARTIAL`, or `NEW_REQUIRED`.

Key result:

- Content-addressed artifact storage is **reuse**, not greenfield work.
- Encrypted/off-device disaster recovery is still a genuine gap.
- Signed portable interchange is partially implemented across prior systems and should be unified in AICCEP's continuity boundary.
- Multiwriter knowledge concurrency remains a genuine gap.
- Relation integrity and manifest semantics need hardening, not parallel implementations.
- JSON-schema governance and single-source schema generation belong under Centinal26 governance.
- Orphan detection belongs in the continuity layer and must be non-destructive before any garbage collection is authorized.

## Entity mapping

Second Brain entities map into canonical state rather than into a second database authority.

Examples:

- `Experiment` and `Run` metadata belong to AICCEP; execution belongs to Centinal26/Frost CORE; immutable outputs belong to Frost CORE.
- `Evidence` metadata and relationships belong to AICCEP; evidence bytes belong to Frost CORE.
- `Artifact` metadata belongs to AICCEP; artifact identity and immutable bytes belong to Frost CORE.
- `Code Module` metadata belongs to AICCEP while source revisions belong to Git.
- Knowledge tasks belong to AICCEP; executable tasks belong to the bounded execution plane.

The metadata/bytes split is intentional. It allows knowledge relationships to evolve without duplicating canonical artifact bytes.

## First adapter boundary

The first integration adapter must be one-way and proposal-only:

`Second Brain v0.2 record -> validate -> map stable identity -> verify artifact hashes -> preserve provenance/revision/epistemic state -> emit canonical proposal`

It must be idempotent. Re-ingesting identical source records must not produce duplicate canonical objects.

The adapter may not:

- rewrite the historical AICCEP database silently;
- create another artifact byte store;
- create another execution runtime;
- resolve contradictions automatically;
- promote epistemic state automatically;
- convert prose into arbitrary shell execution;
- grant execution authority.

## Differential qualification gate

Before any isolated Second Brain runtime is superseded, representative source data must demonstrate:

1. stable or deterministic identity mapping;
2. relationship preservation;
3. revision lineage preservation;
4. epistemic-state preservation;
5. artifact SHA-256 preservation;
6. experiment/run linkage preservation;
7. duplicate-ingest idempotency;
8. failure atomicity;
9. deterministic export of the resulting canonical state.

Physical Android/Termux validation remains a separate gate. Host integration success cannot promote `DEVICE_VALIDATED` or `PERSISTENT_VALIDATED`.

## Next implementation

The next code change should be the smallest read-only/proposal-only adapter satisfying this contract. It should consume Second Brain v0.2 exports or SQLite state without granting write authority to either historical store.

Only after differential tests pass should the genuinely missing roadmap capabilities be implemented.
