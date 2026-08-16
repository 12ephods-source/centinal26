# Base44 evidence mirror trust boundary

Centinal26 treats the append-only event kernel as canonical execution and evidence truth. Base44 entities such as `AutomationRoleResult` and `AutomationVerificationVerdict` are coordination and mirror records. Their administrative RLS permits mutation, so a Base44 row is never sufficient evidence for merge, physical-release, security-review, capability-expansion, or GA authority.

## Required consequential-consumer rule

A consequential consumer MUST fail closed unless all of the following are true:

1. The Centinal26 event chain verifies end-to-end.
2. A trusted canonical reference supplies the exact canonical event ID and event hash. Those values MUST NOT be trusted merely because the Base44 mirror row contains them.
3. The canonical event is `DECISION_RECORDED` and contains a versioned `payload.authority_grant` with `outcome="ALLOW"`, the exact mirror kind/ID, the versioned mirror schema, and the exact authority scope requested.
4. If a legacy/top-level `payload.decision` field is present, it must also be exactly `"allow"`; `deny`, abstain, unknown, or malformed outcomes fail closed.
5. The supplied Base44 row satisfies the entity-kind-specific versioned schema. `AutomationVerificationVerdict` requires its logical `verdict_id`, result/contract identities, verdict, verifier, details, verdict hash, and creation identity. `AutomationRoleResult` requires its logical `result_id`, contract, role, status, payload, result hash, and creation identity. Optional evidence hashes are normalized into the canonical projection. Unknown authority-bearing fields are rejected.
6. `mirror_id` exactly equals the entity's logical stable ID (`verdict_id` for `AutomationVerificationVerdict`, `result_id` for `AutomationRoleResult`). A Base44 storage-row `id` is metadata, not the logical authority identity.
7. The verifier itself constructs the canonical projection from the validated full row. Callers cannot choose a subset of authority fields to hash. Missing required fields, wrong types, malformed JSON payload/details, invalid hashes, unknown schema versions, and ambiguous extra fields fail closed.
8. The canonical event contains `payload.mirror_binding` with the exact mirror schema, entity kind, logical ID, contract ID, related result ID, canonical SHA-256 of the verifier-constructed projection, and requested authority scope.
9. The current validated mirror projection still hashes to the committed digest.
10. The requested authority scope exactly matches both the explicit authority grant and the canonical mirror binding.

`centinal26.mirror_evidence.verify_mirror_evidence()` implements this boundary. A mutable mirror row can coordinate handoffs and status displays, but it cannot create or upgrade authority by itself. Event type alone is never treated as an affirmative authorization. In particular, a generic `VERIFICATION_PASSED` event does not authorize mirror evidence without a separately defined future authority-grant schema.

## Canonical projection versus Base44 metadata

The authority digest is not a hash of an arbitrary caller-selected dictionary. Each supported entity has a fixed versioned projection owned by the verifier. Base44 infrastructure metadata such as storage-row `id`, `created_date`, `updated_date`, `created_by_id`, and `is_sample` may accompany the row but does not define consequential authority. Any new authority-bearing field requires a versioned successor schema rather than being silently ignored.

This distinction closes the partial-projection failure mode: a caller cannot bind only `{"verdict_id": ..., "verdict": "VERIFIED"}` and later omit changes to `contract_id`, `result_id`, verifier/details, hashes, payload/status, or creation identity. Those authority-relevant fields are required and projected by the verifier itself.

## Current production-path audit

At the baseline head used to introduce this boundary, no production file under `src/`, `scripts/`, or `termux/` directly consumes the Base44 `AutomationRoleResult` or `AutomationVerificationVerdict` entity names. `tests/test_mirror_authority_boundary.py` locks that invariant: future direct consumers fail CI unless they are routed through the canonical binding gate.

This means Base44 remains adapter/control-plane infrastructure rather than the system of record. New Base44 consumers must carry a canonical event identity/hash and use the gate before a mirror result can influence authorization or promotion.

## Failure semantics

The verifier rejects, at minimum:

- missing canonical event identity or hash;
- an invalid/tampered canonical hash chain;
- a missing canonical event;
- an event-hash mismatch;
- a non-authority event type;
- a missing or malformed explicit authority grant;
- any non-affirmative top-level decision when that compatibility field is present;
- authority-grant schema, outcome, mirror identity, mirror-schema, or scope disagreement;
- a partial mirror record or missing authority-relevant field;
- wrong mirror field types or malformed JSON payload/details;
- invalid result/verdict/evidence hashes;
- unknown or ambiguous authority-bearing mirror fields;
- logical `verdict_id`/`result_id` disagreement with `mirror_id`;
- a missing or structurally different mirror binding;
- an admin-edited or stale mirror projection whose SHA-256 no longer matches;
- contract/result identity disagreement;
- authority-scope disagreement.

The mirror record is not rewritten to resolve disagreement. Canonical/mirror conflict is evidence of drift or tampering and must be reconciled by producing new canonical evidence, not by treating the mutable mirror as truth.
