# Centinal26 Objective Integrity — Native Integration Plan

Status: CANDIDATE / NOT MERGED
Date: 2026-08-19

## Finding

Centinal26 already has three adjacent controls:

1. `src/frost_core/intelligence_controller.py` is a persistent scheduler and explicitly does not grant execution authority.
2. `src/frost_core/capability_factory.py` is a fail-closed capability promotion ledger; discovery is inventory only.
3. `src/frost_core/object_store.py` provides immutable content-addressed objects, append-only provenance, explicit links, mutable aliases with alias history, and SHA-256 object identity.

Objective Integrity therefore must not become a second scheduler, replacement capability factory, or parallel evidence store.

## Native placement

Add `src/frost_core/objective_integrity.py`, `schemas/objective.schema.json`, and `tests/test_objective_integrity.py`, then wire objective authorization into the invocation/effect boundary.

The standalone prototype hash-chain log remains useful as a compatibility/export artifact, but canonical objective proposals, authorization decisions, and authorized objectives should use `CanonicalObjectStore`.

## Security model

Any source may submit an objective proposal. Proposal content is never proof of authority.

`OWNER` and `OWNER_POLICY` are source classes, not authentication results. A separate `AuthorizationVerifier` validates a signed/attested authorization reference outside untrusted proposal data.

Decision rules:

- non-owner source → `PROPOSE_ONLY`
- unknown canonical root → `QUARANTINE`
- failed authorization verification → `QUARANTINE`
- forbidden privileged capability request → `DENY`
- verified owner/policy + known root + bounded capabilities → `EXECUTE`

## Capability promotion is not objective authorization

Do not add a global `objective_authorized` flag to `CapabilityFactoryLedger.REQUIRED_PROMOTION_GATES`.

Capability promotion answers whether a capability is technically trustworthy and callable. Objective authorization answers whether a particular invocation serves an authenticated owner-approved objective. A promoted capability must not inherit authority across unrelated future objectives.

## Required invocation contract

Consequential execution requests should carry:

- `objective_object_id`
- `objective_evaluation_id`
- `root_objective`
- `capability_token`
- `authorization_ref`
- `source_event_key` when applicable

Immediately before side effects, the executor resolves the authorized objective and validates the requested action against the capability token.

## Controlled-evolution hardening

`controlled_evolution_hard.py` already serializes repository content as `UNTRUSTED_DATA` and explicitly tells the proposer not to follow embedded instructions, commands, policy changes, credential requests, or authority claims. Preserve this boundary.

After integration, hard-protect the objective-integrity implementation, owner-authorization verifier, canonical root configuration, objective schema, and invocation-time authority verifier. Ordinary controlled evolution must not rewrite its own authority boundary.

## Migration sequence

1. Preserve the current standalone bundle as provenance evidence and prototype.
2. Add repository-native Objective Integrity module/schema/tests without changing runtime behavior.
3. Bind proposals and decisions to `CanonicalObjectStore`.
4. Carry authorized-objective references in consequential execution envelopes.
5. Enforce objective + capability-token checks at the effect/provider boundary.
6. Hard-protect the authority implementation from ordinary controlled evolution.
7. Add adversarial CI cases for self-promotion, imported instructions, fake owner claims, capability amplification, network-scope escape, forbidden credential/secret actions, missing/corrupted objective references, cross-root invocation, and revocation/supersession.
8. Update `provenance/ARTIFACT_REGISTRY.json` and release evidence only after repository security gates pass.

## Canonical root policy

Current candidate roots:

- `automation_os`
- `frost_learning_os`
- `sdos_verification`
- `physics_research`

The root set is owner-authority configuration and cannot be modified through ordinary agent proposals.

## Attribution boundary

The system does not need attacker attribution before rejecting an unauthorized objective.

`unauthorized objective != established attacker attribution`

Authorization is an execution decision. Attribution is a separate forensic question.
