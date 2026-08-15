# Callable Fabric Source Attestation

Status: implementation candidate on `agent/provider-source-attestation`

## Problem

The connected GitHub provider historically returned the semantic core's pinned `canonical_git_sha` and `source_identity_sha256`, plus the request-trigger commit as `provider_sha`.

Those values answer different questions and must not be conflated:

- semantic-core identity: which canonical semantic fabric the provider imports;
- provider execution identity: which actual worker/workflow bytes performed and transported the invocation;
- trigger identity: which checked-out runtime commit caused this execution.

A newer provider wrapper can legitimately execute an older pinned semantic core. Reporting only the semantic-core commit makes the newer wrapper invisible to provenance review.

## Attestation schema

Every GitHub worker result now includes `source_attestation` with schema:

`frost-source-attestation/1.0`

### semantic_core

- `canonical_git_sha` — the semantic core's pinned canonical source commit;
- `source_identity_sha256` — existing canonical semantic source identity;
- `deployment_adapter_sha256` — existing semantic adapter spec identity;
- `file_sha256` — SHA-256 of the actual `fabric.js` bytes imported by the worker.

### provider_runtime

- `provider` — `github-actions`;
- `worker_source_sha256` — SHA-256 of the executing `worker.js` bytes;
- `workflow_source_sha256` — SHA-256 of the active workflow file bytes in the checked-out runtime tree;
- `checked_out_sha` — GitHub's commit SHA for the checked-out execution/trigger tree;
- `checked_out_ref` — GitHub's execution ref.

### provider_code_identity_sha256

Composite SHA-256 over canonical JSON containing:

- provider name;
- semantic-core file SHA-256;
- worker source SHA-256;
- workflow source SHA-256.

This identity changes if any of those execution-critical code artifacts change.

## Compatibility

Existing top-level fields remain present for consumers that already depend on them:

- `canonical_git_sha`
- `source_identity_sha256`
- `deployment_adapter_sha256`
- `provider_sha`

The new attestation does not redefine those fields. It makes their scope explicit.

## Verification

The GitHub worker doctor independently hashes the semantic core, worker, and workflow from disk, reconstructs the composite identity, and verifies that the emitted attestation matches those actual bytes.

The outer envelope hash covers the entire attestation.

## Idempotency interaction

When an identical request is reconciled from a prior immutable result, the prior result bytes — including its original source attestation and execution identity — are preserved. This is intentional: reconciliation is evidence that the earlier execution result was reused, not a claim that a new execution occurred under the current trigger.

## Epistemic rule

A semantic-core commit must not be presented as the provider deployment commit. A trigger commit must not be presented as the semantic-core commit. File-level execution identities and semantic source identities are separate evidence fields.
