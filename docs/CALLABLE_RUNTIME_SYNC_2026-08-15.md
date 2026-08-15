# Callable Runtime Selective Deployment Sync — 2026-08-15

## Purpose

Synchronize only the promoted GitHub Callable Fabric hardening files from canonical `main` into the active `callable-runtime` deployment branch while preserving immutable runtime requests/results and avoiding unrelated application changes.

## Source and base

Canonical promoted source through:

`28562c74a3d5f5da6c043b927512539e3ecca5d7`

Runtime deployment base before this sync:

`06aa35f2fbdcaba08da5b9695e6906576673b33d`

## Exact promoted blobs

- `deploy/github/callable-worker-v1.0.0/worker.js`
  - blob: `5e30948d37513d5cf69f84beaad01bb4e3445997`
- `deploy/github/callable-worker-v1.0.0/doctor.js`
  - blob: `bbf3e79ad019199a250cfe7baf531ebd175da09b`
- `.github/workflows/callable-fabric-worker.yml`
  - blob: `0d33b08d7e9b24e1fdad9bd4404011c599886aa0`
- `tests/test_callable_backlog_recovery.py`
  - blob: `d2a5c4e3ae52fcd3e7fd15d486881166f0f695ce`

## Promoted semantics

1. canonical request hashing and bounded idempotency keys;
2. same key + same hash -> reuse prior verified immutable result;
3. same key + different hash -> `IdempotencyConflict`;
4. push, manual, and hourly backlog wake-ups;
5. fixed checkout of `callable-runtime` for all worker triggers;
6. static serialized concurrency with no in-flight cancellation;
7. 20-minute worker timeout;
8. bounded fetch/rebase/push result reconciliation retry;
9. existing Guardian and semantic-tool-only execution boundary retained.

## Excluded from this sync

The sync does not merge unrelated `main` history into `callable-runtime`. Immutable request/result records already present on the runtime branch remain part of that branch history.

## Remaining boundary

The provider still does not claim transactional exactly-once external side effects across a crash after execution but before durable result publication. Connected capabilities remain semantic/read-only until a durable execution-intent/acknowledgement protocol or provider-native side-effect idempotency is implemented.
