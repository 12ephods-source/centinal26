# GitHub Callable Fabric — Durable Request Idempotency

Status: implementation candidate on `agent/github-callable-idempotency`

## Problem

The connected GitHub worker historically skipped only requests whose *result filename* already existed. Two different immutable request files could therefore carry the same semantic request and invoke the operation twice.

## Identity rule

Each request now has:

- `request_sha256` — SHA-256 of canonical request JSON;
- `idempotency_key` — explicit top-level key, then `context.idempotency_key`, otherwise the request hash.

The key is bounded to 256 UTF-8 bytes.

## Reconciliation rule

Before invocation, the worker scans already-verified immutable result envelopes in `runtime/results/`.

- same idempotency key + same request hash: reuse the prior immutable result bytes; do not invoke again;
- same idempotency key + different request hash: emit an `IdempotencyConflict` result; do not invoke;
- no matching result: execute normally.

This also deduplicates multiple equivalent request files processed in the same workflow run because earlier result files are visible to later loop iterations.

## Boundary

This closes duplicate execution *after a durable result exists*. It does not claim transactional exactly-once side effects across a runner crash between provider execution and committing the result to Git.

The currently connected operation set is intentionally semantic/read-only, with the destructive operation serving only as a Guardian negative control and having no destructive implementation. Any future side-effecting connected capability must add provider-native idempotency or a durable execution-intent/acknowledgement protocol before it is enabled through this worker.

## Security

Only cryptographically valid Frost result envelopes participate in deduplication. Malformed or unverifiable files are ignored as reconciliation evidence.
