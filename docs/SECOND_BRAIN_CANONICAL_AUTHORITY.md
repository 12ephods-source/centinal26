# AI-First Second Brain canonical authority map

Status: HOST_VERIFIED_EXTERNAL_GATES_PENDING

Machine-readable authority: `automation/SECOND_BRAIN_AUTHORITY.json`.

## Canonical decision

AI-First Second Brain v0.2.0 and historical AICCEP-OS remain migration, provenance, and domain-semantics sources. They are not parallel live canonical runtimes. `automation/PROJECT_STATE.json` remains the machine continuation authority; Centinal26/Frost CORE remain the bounded execution and artifact-identity path.

The historical AICCEP database must not be silently rewritten. Historical records enter through provenance-preserving, proposal-only adapters.

## Verified integration state

The authority map, generic proposal-only adapter, direct Second Brain v0.2 `export-context` bridge, and host continuity-hardening tranche are now integrated.

- The direct v0.2 bridge preserves complete source records, deterministic per-record hashes, epistemic state, relationships, and declared artifact hashes without granting execution or truth-promotion authority.
- Content-addressed storage remains reused rather than duplicated.
- Signed portable continuity bundles, optimistic compare-and-swap, typed relations, governed JSON schemas, hardened manifests, and single-source schema generation are host-qualified and canonical.
- Integrity/orphan reconciliation is deliberately non-destructive; garbage collection authority remains false.
- Encrypted-backup handling delegates to the external `age` provider and fails closed when that provider is unavailable. No plaintext fallback exists.

Exact continuity-hardening qualification was performed on head `3838b20ce9cbddb9ee5d73432726248dd88398e5`, then merged to production as `8c07f2f89de638f5d2b4e464250b7cf838d5f070`. CI, Automation Validation, validate, automation-gates, federation-gates, and Mature Product Qualification all passed; Ruff and pytest passed on Python 3.11, 3.12, and 3.13.

## Remaining partial boundaries

Roadmap rank 11 remains partial: the host delegation contract is verified, but real `age` encryption, independent off-device replication, retrieval, decryption, and recovery have not been observed.

Roadmap rank 17 remains partial: structural/orphan diagnostics are verified, but destructive garbage collection is not authorized.

Physical Android/Termux validation remains separate. Host or CI success cannot promote `DEVICE_VALIDATED` or `PERSISTENT_VALIDATED`; the canonical tracker remains issue #208.

## Current terminal boundary

No further architecture expansion is required by this integration plan. Resume this line only when one of the following external evidence conditions is available:

1. a real `age` provider plus an independently identified off-device target can complete encryption, replication, retrieval, re-hash, decryption, and recovery verification; or
2. device-origin evidence from the authorized Android/Termux physical gate in issue #208 is available, followed separately by reboot-persistence evidence.

Until then, the correct state is host integration verified with external and physical gates pending.
