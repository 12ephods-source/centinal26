# Dedupe/Organizer Canonical Store v1

## Purpose

This is the first operational persistence layer for the Dedupe/Organizer canonical kernel. It stores only bundles that already satisfy the canonical invariant validator and keeps authoritative state separate from rebuildable projections.

It is intentionally not a remediation engine, deletion tool, or semantic truth oracle.

## Trust boundary

The store may:

- initialize a local SQLite database;
- ingest invariant-valid canonical objects, provenance events, and filter decisions;
- reject stable identifiers reused with different content;
- re-ingest identical records idempotently;
- read canonical objects;
- rebuild disposable query/search projections;
- report store counts.

The store may not:

- delete canonical records;
- interpret duplicate detection as filesystem deletion authority;
- promote a claim to VERIFIED;
- invent provenance;
- mutate an existing canonical object, provenance event, or filter decision;
- treat its projection table as authoritative state;
- perform Guardian/Sentinel remediation.

## SQLite model

Authoritative/append-only tables:

- `canonical_objects`
- `provenance_events`
- `object_provenance`
- `filter_decisions`

Disposable projection:

- `object_projection`

`object_projection.authoritative` is constrained to `0`. It can be deleted and rebuilt without affecting canonical state.

## Ingest semantics

Before any transaction, the entire supplied bundle is evaluated by `validate_canonical_kernel.validate_bundle`.

If validation fails, no records are admitted.

For a stable ID already present:

- exact same content/envelope => idempotent no-op;
- different content hash or serialized canonical record => fail closed.

The same rule applies to provenance-event IDs and filter-decision IDs.

## CLI

```bash
python scripts/canonical_store.py --db canonical.db ingest examples/canonical_bundle.valid.json
python scripts/canonical_store.py --db canonical.db rebuild-projection
python scripts/canonical_store.py --db canonical.db stats
python scripts/canonical_store.py --db canonical.db get obj_summary
python scripts/canonical_store.py --db canonical.db search "derived example"
```

There is deliberately no delete command.

## Relationship to project federation

The cross-project federation registry identifies Dedupe/Organizer as the shared canonicalization/provenance capability. This store implements a local durable substrate for those typed objects without merging project trust domains or transferring mutation authority.

A Physics, Cybersecurity, OpenQuest, or Automation record may be stored under the common envelope, but its domain-specific scientific, forensic, security, licensing, or deployment gate remains owned by that domain.

## Qualification boundary

Tests establish software properties only:

- valid bundle round-trip;
- identical re-ingest idempotency;
- object-ID mutation rejection;
- envelope mutation rejection;
- provenance-event mutation rejection;
- filter-decision mutation rejection;
- invalid-bundle transaction rejection;
- projection rebuildability/non-authority;
- absence of a delete CLI surface;
- multiple independent canonical bundle ingestion.

Passing these tests does not establish semantic truth, scientific validity, forensic attribution, Android device execution, or production deployment.
