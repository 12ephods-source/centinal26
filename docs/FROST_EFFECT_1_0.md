# frost-effect/1.0 — consequential execution protocol

Status: **HOST IMPLEMENTED / EXTERNAL SIDE EFFECTS STILL GATED**

`frost-effect/1.0` closes the host-side correctness gap between an authorized semantic
request and a consequential external mutation. It does **not** make arbitrary shell
execution available and it does not itself call external providers.

The protocol separates these durable facts:

`request -> authorization -> claim -> persisted execution intent -> provider execution`
`-> execution receipt -> independent verification -> publication -> acknowledgement`

## Crash boundary

Before calling an external provider the worker must durably persist an execution intent
containing a provider idempotency identity. If the worker disappears while the record is
`EXECUTING`, recovery moves the effect to `RECOVERY_REQUIRED`; it is never silently
resubmitted.

The adapter must then establish one of:

- `NOT_EXECUTED`: the provider confirms no effect happened; a bounded retry may proceed;
- `EXECUTED`: the provider returns the immutable result/receipt, which is recorded and
  independently verified;
- `UNKNOWN`: state remains `RECOVERY_REQUIRED` and fails closed.

This is the key difference between ordinary retry and safe consequential execution.

## State model

- `PENDING_AUTHORIZATION`
- `AUTHORIZED`
- `CLAIMED`
- `EXECUTING`
- `RECOVERY_REQUIRED`
- `EXECUTED`
- `VERIFIED`
- `PUBLISHED`
- `ACKNOWLEDGED`
- `DENIED`
- `FAILED_RETRYABLE`
- `FAILED_TERMINAL`
- `VERIFICATION_FAILED`
- `CANCELLED`

`EXECUTED` is not `VERIFIED`; `VERIFIED` is not delivered; `PUBLISHED` is not
acknowledged.

## Idempotency

The request idempotency key is bound to the complete immutable request SHA-256. Reusing
the same key with different content is rejected. Provider-side side effects additionally
receive a durable provider idempotency key before execution.

## Authorization

Authorization is immutable and bound to the request SHA-256, capability, actor, and
expiry. A remote caller cannot authorize itself by placing an `approved=true` field in a
request.

## Audit

Every transition is appended to a global SHA-256 hash-linked history ledger. Historical
records are not rewritten when current state changes.

## Promotion boundary

Host implementation and tests do not authorize Cloudflare, GitHub, Base44, device, or
other external mutations. Each side-effecting capability still requires:

1. a narrow semantic operation;
2. explicit Guardian policy;
3. provider adapter idempotency/reconciliation support;
4. independent postcondition verification;
5. real connected validation;
6. capability-specific promotion.

No unrestricted remote shell is part of this protocol.
