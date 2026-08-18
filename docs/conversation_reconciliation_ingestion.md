# Conversation reconciliation ingestion

This integration imports ChatGPT conversation-reconciliation output into the existing Centinal26 evidence substrate without creating a second source of truth.

## Boundary

The standalone reconciler is an evidence-acquisition and serialization tool. Centinal26 remains authoritative for immutable objects, provenance, aliases, execution state, and control-plane reconciliation.

`ConversationEvidenceIngestor` writes reconciliation-derived records into `CanonicalObjectStore` using the evidence class `SECONDARY_RECONCILIATION`.

It deliberately does **not**:

- advance `project/current` or any other alias;
- declare a project assignment canonical;
- mark a contradiction resolved;
- enable a reusable capability;
- execute a proposed action;
- delete or rewrite earlier evidence.

## Imported object kinds

- `conversation_reconciliation`
- `project_assignment_candidate`
- `conversation_claim`
- `conversation_contradiction`
- `conversation_decision`
- `conversation_artifact_reference`
- `conversation_reusable_candidate`

The reconciliation object links to the derived child objects. The complete source state may still be retained by the upstream reconciliation bundle; these child objects are normalized evidence projections for Centinal26 workflows.

## Promotion rule

Project assignment, capability registration, canonical artifact selection, action execution, and contradiction resolution remain downstream decisions governed by the existing Centinal26 control and verification machinery.

A reconciliation report cannot validate itself merely by being ingested. `SECONDARY_RECONCILIATION` is intentionally weaker than direct execution evidence.

## Migration direction

Stable reconciler functions should migrate toward thin adapters over Centinal26 primitives:

1. acquire/export conversation evidence;
2. validate the reconciliation bundle at the ingress boundary;
3. import normalized evidence through `ConversationEvidenceIngestor`;
4. use Centinal26 object/provenance storage and event state for durable ownership;
5. resolve project/canonical/action decisions through existing bounded control paths.

This avoids maintaining parallel artifact stores, project authorities, or execution ledgers.
