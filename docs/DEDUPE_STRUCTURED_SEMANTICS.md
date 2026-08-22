# Dedupe/Organizer Structured Semantic Derivation v1

## Purpose

This layer closes the narrow semantic-dedupe and contradiction-preservation gap without introducing free-text guessing, deletion authority, or semantic truth promotion.

## Semantic contract

Only explicit structured `CLAIM.payload` fields participate:

- `subject_ids`
- `predicate`
- `object_value`
- optional `comparison_mode`

Two claims are a deterministic structured-semantic duplicate when their sorted `subject_ids`, exact `predicate`, and canonical JSON `object_value` are identical. Their prose `statement` may differ.

This is deliberately narrower than embedding/model similarity. Free text alone is not deduplicated and no synonym or ontology inference is performed.

## Contradiction contract

A contradiction is derived only when claims:

1. have the same sorted `subject_ids` and exact `predicate`;
2. explicitly declare `comparison_mode=EXCLUSIVE_VALUE`; and
3. contain at least two different canonical `object_value` values.

The derived contradiction remains `UNRESOLVED`; no winner is selected. Different values are not presumed contradictory unless the source claims explicitly opt into exclusive-value semantics.

## Outputs

The program preserves all input objects and appends only derived objects:

- `DUPLICATE_GROUP / STRUCTURED_CLAIM_DUPLICATE`
- `CONTRADICTION / EXCLUSIVE_STRUCTURED_CLAIM_CONFLICT`

Every generated object:

- is `epistemic_status=DERIVED`;
- is `verification_status=UNVERIFIED`;
- is `authority_class=DERIVED_RECORD` and `authoritative=false`;
- names an explicit provenance event;
- has stable deterministic identity based on structured inputs;
- declares `mutation_authority=NONE`;
- preserves every source claim.

No filter decision, merge, deletion, quarantine, or remediation action is generated.

## Determinism and idempotency

Member IDs are sorted before identity construction. Timestamps are deterministically inherited from source ingestion/creation times. Running the derivation over an already enriched bundle must return an identical bundle. Reordering source objects must not change derived relationship IDs.

The enriched bundle is validated against the canonical-kernel cross-object invariants before it is returned. It can then be admitted to the append-only canonical store; identical re-ingest is an idempotent no-op.

## CLI

```bash
python scripts/structured_semantic_dedupe.py input_bundle.json --output enriched.json
python scripts/structured_semantic_dedupe.py input_bundle.json --db canonical.db
```

The second form derives and ingests through the existing append-only canonical store. There is no delete command.

## Epistemic boundary

A duplicate group means only that explicitly structured fields are equal under this rule. A contradiction means only that explicitly exclusive structured fields disagree. Neither result proves the real-world truth or falsity of any member claim.

Software PASS for this layer establishes deterministic implementation behavior, not scientific validity, forensic attribution, physical-device validation, or truth of stored claims.
