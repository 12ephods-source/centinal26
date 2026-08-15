# Callable Fabric Request Expiry / Stale-Request Gate

Status: implementation candidate on `agent/callable-stale-request-gate`

## Problem

A durable queue can preserve a request longer than the intent that created it remains valid. Without an explicit deadline, a previously queued request may execute after an outage or backlog recovery even when the caller would no longer want the action performed.

## Contract

`frost-call/1.0` requests may optionally include:

```json
{
  "context": {
    "expires_at": "2026-08-15T03:00:00Z"
  }
}
```

`expires_at` must be an RFC3339 timestamp with an explicit timezone (`Z` or numeric offset).

Requests that omit `context.expires_at` retain the previous behavior. No implicit expiration is invented for legacy requests.

## Precedence

Durable idempotency reconciliation occurs before expiry evaluation.

This yields the required semantics:

- same idempotency key + same request hash + existing verified result: reuse the immutable prior result even if the current retry occurs after `expires_at`;
- no existing result + current time before `expires_at`: execute normally;
- no existing result + current time at or after `expires_at`: emit a terminal `StaleRequest` result without invoking the semantic operation;
- malformed `expires_at`: emit `InvalidExpiry` without invocation.

A deadline therefore prevents late first execution. It does not retroactively invalidate an already established execution result.

## Evidence

Fresh and expired decisions preserve `request_expiry` in the result envelope:

```json
{
  "status": "FRESH | EXPIRED",
  "expires_at": "...",
  "observed_at": "..."
}
```

Malformed deadlines preserve:

```json
{
  "status": "INVALID",
  "expires_at": "..."
}
```

The outer envelope hash covers this evidence.

## Independent verification

The independent verifier re-parses the request deadline rather than trusting the worker label.

For `FRESH` it requires:

`observed_at < expires_at`

For `EXPIRED` it requires:

`observed_at >= expires_at`

and a `StaleRequest` error.

For malformed deadlines it requires `InvalidExpiry` plus `INVALID` status.

A forged stale/fresh decision remains rejectable even if an attacker recomputes the ordinary envelope hash after changing the timestamps.

## Recovery interaction

Hourly/manual backlog recovery may encounter old requests. Requests with explicit expired deadlines become terminal stale results and are independently verified; they are not repeatedly retried forever.

Requests without deadlines remain eligible for recovery because the system cannot infer that the original intent expired.

## Side-effect boundary

This is a prerequisite for safe future side-effecting capabilities, not sufficient authorization for them. Side-effecting execution still requires durable execution-intent/acknowledgement semantics or provider-native idempotency before enablement.
