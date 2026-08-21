# Condition-Watch Durable Delivery Outbox

Status: implemented on `main`; lease-completion fencing is required.

## Problem

A terminal observation and successful downstream notification delivery are not the same event. The original condition-watch ledger stored `terminal_notified_at` in the observation transaction. If a worker crashed or the notifier failed after that transaction but before delivery completed, subsequent polls could suppress the only notification.

## Invariant

The repaired path is:

`terminal observation -> durable PENDING outbox -> DELIVERING lease -> explicit DELIVERED acknowledgement`

`terminal_notified_at` is written only after an acknowledgement.

## Delivery states

- `PENDING` — durable work exists and may be claimed.
- `DELIVERING` — one worker owns a bounded lease.
- `DELIVERED` — downstream delivery was explicitly acknowledged.
- `FAILED_TERMINAL` — delivery cannot be retried automatically.
- `LEGACY_UNCERTAIN` — a pre-outbox record says the old caller was told to notify, but no downstream acknowledgement evidence exists.

Expired `DELIVERING` leases are reclaimable by another worker. Retryable failures return to `PENDING`.
Every acknowledgement or failure must present the `attempt_count` captured in its
`DeliveryClaim`, in addition to the delivery and worker identifiers. This fences a
late completion from an expired attempt even when a restarted or concurrent worker
reuses the same configured worker ID.

## Exactly-once scope

The ledger guarantees one durable outbox item per immutable `target_key`. It does not claim provider-wide exactly-once side effects. Downstream notification transports should use the stable `delivery_id` as their own idempotency key when they support one.

## Legacy migration

Version-1 rows populated `terminal_notified_at` before acknowledgement semantics existed. Migration preserves that timestamp as `terminal_enqueued_at`, clears the unsupported delivered claim, and creates a `LEGACY_UNCERTAIN` outbox item. An operator or higher-level reconciler must explicitly resolve each legacy delivery as delivered or requeue it.

This avoids silently treating unknown historical delivery as either success or failure.

## Failure boundary

A successful observation commit is insufficient to mark a terminal notification delivered. A successful notifier call is also insufficient unless the caller records the acknowledgement. The durable outbox is the handoff boundary between those operations.
