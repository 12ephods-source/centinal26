# Automation Intelligence Controller

The Automation Intelligence Controller is the persistent scheduling and coverage layer for Frost Automation OS / Centinal26. It converts observations into deduplicated work at latency appropriate to the event instead of running one large prompt at one fixed cadence.

## Invariant

The controller may observe, classify, prioritize, queue, lease, and record work. It does **not** grant itself execution authority. Consequential execution still flows through the existing authorization, bounded capability, verification, evidence, and audit boundaries.

## Event-latency policy

| Event/work class | Dispatch target |
| --- | --- |
| state change | immediate |
| critical contradiction | immediate |
| material new evidence | immediate |
| ordinary conversation review | 10-minute batch |
| deep synthesis | hourly |
| portfolio review | daily |
| scientific compatibility review | daily |
| full corpus audit | weekly |
| architecture review | monthly |

`run_forever()` may poll frequently (for example every 10 seconds), but deterministic work keys ensure that periodic work is emitted only once per logical cadence window. Immediate work is created by observations rather than by waiting for a periodic review.

## Persistent state

The SQLite ledger stores:

- cadence policies;
- canonical source snapshots and content hashes;
- append-only, SHA-256 hash-linked change events;
- separate mutable event-processing status;
- Automation conversation registry and per-week reviews;
- leased work items with deterministic idempotency keys;
- controller-cycle records and hashes.

SQL triggers prohibit mutation or deletion of recorded change events. Processing status is intentionally stored separately so acknowledgement does not rewrite evidence.

## Conversation coverage

Conversation selection is deterministic:

`P0 -> P1 -> P2 -> P3 -> strategic_value descending -> conversation_key`

A conversation already reviewed during the current ISO week is skipped while eligible unreviewed conversations remain. The controller does not mark inaccessible conversation material reviewed. Content acquisition remains an adapter responsibility: ChatGPT project context, an authorized export, Base44, File Library ingestion, or another provider can supply records without changing the controller core.

## CLI

Install the project and use the dedicated entry point:

```bash
centinal26-intelligence init
centinal26-intelligence status
centinal26-intelligence cycle
centinal26-intelligence next-review
centinal26-intelligence due
```

Register a conversation:

```bash
centinal26-intelligence register automation-thread "Automation Thread" \
  --review-class P1 --strategic-value 0.9
```

Record an observation:

```bash
centinal26-intelligence observe WORKER android-termux CRITICAL_CONTRADICTION HIGH \
  --evidence '{"android_termux_worker_seen":false}' \
  --contradiction '{"expected":"android/termux","observed":"not observed"}'
```

Run the local controller loop:

```bash
centinal26-intelligence daemon --poll 10
```

The loop prints a cycle only when new or due work exists. It does not call arbitrary shell commands or silently promote a task to execution.

## Work lifecycle

A provider can use:

```text
QUEUED -> RUNNING (lease) -> COMPLETE
```

Expired leases can be reclaimed. `work_key` is unique, so repeated polling does not create duplicate scheduled work for the same logical window. Change events use a deterministic content-derived dedupe key.

## Integration boundaries

- **Centinal26 event state:** remains the canonical execution/project event kernel. The intelligence controller does not replace `EventStore` or `advance_until_idle`.
- **Frost CORE condition watch:** remains the terminal-condition / exactly-once delivery primitive. The controller provides broader event-latency and corpus scheduling.
- **Base44:** can mirror or feed conversation, worker, job, validation, and evidence state through adapter code; credentials are not embedded here.
- **ChatGPT:** can claim review/synthesis work and return structured results when available.
- **Termux/Android:** can run the daemon and claim allowlisted work, but device capability is not inferred from host execution.

## Validation boundary

The controller core is covered by deterministic tests for immediate dispatch, change deduplication, weekly conversation priority, exactly-once cadence windows, lease recovery, processing acknowledgement, and immutable change-event history.

Host tests do **not** establish Android/Termux physical validation. Device promotion still requires real worker heartbeat, real claimed/completed jobs, persistence/reboot evidence, postconditions, and the existing Centinal26 promotion gates.
