# Defensive Repair Evidence Contract v1

Status: CANONICAL_CANDIDATE

The defensive repair capability is fail-closed and restricted to explicitly authorized artifacts. Analyzer or repair-generator output is never sufficient for promotion.

## Required lifecycle

`AUTHORIZED -> AUDIT/CANDIDATE -> REPRODUCED -> CANDIDATE_REPAIR -> INDEPENDENTLY_VERIFIED | VERIFICATION_FAILED`

## Required evidence

Every promotable result must bind:

- authorization scope and artifact/fixture identity;
- original source SHA-256;
- deterministic reproducer result;
- candidate repair SHA-256;
- patch SHA-256;
- regression outcomes;
- independent verifier outcome;
- terminal status.

Evidence serialization must be canonical/deterministic for identical semantic inputs. Environment-specific metadata must not change the canonical evidence digest.

## Trust separation

`software.audit`, `software.reproduce`, and `software.repair` may create candidate evidence only. They do not certify their own output. Only `software.verify`, using the independent verification path, may produce `INDEPENDENTLY_VERIFIED`.

## Authority boundary

The initial adapter is deliberately narrower than a general vulnerability-analysis system. It accepts only the pinned repository-owned known-ground-truth fixture and exposes no arbitrary source input, network targeting, credential access, exploit deployment, or shell authority. Any future expansion requires a separate explicit authorization and containment design.

## Promotion invariant

A result is promotable only when all identity, reproduction, repair, regression, and independent-verification checks pass. Any missing, malformed, altered, or unauthorized evidence fails closed.
