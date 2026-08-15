# Base44 evidence mirror trust boundary

Centinal26 treats the append-only event kernel as canonical execution and evidence truth. Base44 entities such as `AutomationRoleResult` and `AutomationVerificationVerdict` are coordination and mirror records. Their administrative RLS permits mutation, so a Base44 row is never sufficient evidence for merge, physical-release, security-review, capability-expansion, or GA authority.

## Required consequential-consumer rule

A consequential consumer MUST fail closed unless all of the following are true:

1. The Centinal26 event chain verifies end-to-end.
2. A trusted canonical reference supplies the exact canonical event ID and event hash. Those values MUST NOT be trusted merely because the Base44 mirror row contains them.
3. The canonical event is an authority-bearing `DECISION_RECORDED` or `VERIFICATION_PASSED` event.
4. The canonical event contains `payload.mirror_binding` with the exact mirror entity kind, stable mirror ID, canonical SHA-256 of the complete mirror record, and the exact authority scope being requested.
5. The current mirror row still hashes to the committed digest.
6. The requested authority scope exactly matches the canonical binding.

`centinal26.mirror_evidence.verify_mirror_evidence()` implements this boundary. A mutable mirror row can coordinate handoffs and status displays, but it cannot create or upgrade authority by itself.

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
- a missing mirror binding;
- an admin-edited or stale mirror record whose SHA-256 no longer matches;
- mirror-kind or mirror-ID disagreement;
- authority-scope disagreement.

The mirror record is not rewritten to resolve disagreement. Canonical/mirror conflict is evidence of drift or tampering and must be reconciled by producing new canonical evidence, not by treating the mutable mirror as truth.
