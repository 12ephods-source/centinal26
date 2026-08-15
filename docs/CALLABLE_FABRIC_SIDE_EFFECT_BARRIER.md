# GitHub Callable Fabric Side-Effect Barrier

Status: implementation candidate on `agent/callable-side-effect-barrier`

## Purpose

The connected GitHub provider is currently proven for semantic/read-only work. It must not silently become a side-effecting execution provider merely because a future semantic operation is added to the shared fabric.

Until a durable side-effect execution-intent / acknowledgement protocol exists, the provider therefore fails closed on unapproved executable operations.

## Pinned semantic core

The provider effect policy trusts exactly one reviewed semantic-core file identity:

`6e3c6dd26f472456f38b1504d12b1e36723494d663426a8fa8d5eb37f413e5a8`

If the actual imported `fabric.js` SHA-256 differs, executable calls are blocked as:

`SemanticCorePolicyDrift`

This prevents a semantic-core update from inheriting provider execution authority merely by keeping old operation names or risk labels.

## Explicitly approved read-only operations

Under the pinned semantic core only:

- `system.health`
- `system.capabilities`
- `frost.diagnostics.echo`
- `frost.diagnostics.sha256`
- `frost.diagnostics.canonicalize`

These receive provider policy status:

`READ_ONLY`

## Guardian negative control

The existing operation:

`frost.diagnostics.dangerous_demo_policy_test`

is the sole non-read-only exception because, under the exact pinned semantic-core bytes, its implementation explicitly performs no destructive action.

It receives:

`EFFECT_FREE_NEGATIVE_CONTROL`

The provider still does not bypass Guardian. An ordinary operator request remains Guardian-denied. An explicitly approved admin request reaches the semantic implementation but still returns `executed:false`.

If the semantic-core bytes change, this exception disappears automatically until the provider policy is reviewed and repinned.

## Default for future executable operations

Any executable operation not in the explicit read-only set or effect-free negative-control set is blocked before semantic invocation:

`SideEffectProtocolRequired`

with:

`required_protocol = frost-effect/1.0`

`frost-effect/1.0` is intentionally not represented as implemented by this change. The status names the future durability boundary that must exist before side effects can be enabled.

## MCP

The same operation allow policy applies to MCP `tools/call` after deterministic tool-name normalization.

MCP `initialize` and `tools/list` remain control-plane read-only. Non-executing unknown control-plane methods may reach the MCP method-not-found response, but executable unknown tools are fail-closed.

## Evidence

New worker results preserve `provider_effect_policy` in the hashed result envelope.

Examples:

- `READ_ONLY`
- `EFFECT_FREE_NEGATIVE_CONTROL`
- `SIDE_EFFECT_PROTOCOL_REQUIRED`
- `SEMANTIC_CORE_POLICY_DRIFT`

## Independent verification

The independent verifier does not import the worker's policy implementation.

It maintains its own pinned semantic-core hash and approved operation sets, reads the historical worker/core bytes from `provider_sha`, and recomputes the expected provider decision.

For a barrier-capable historical worker, missing or mismatched `provider_effect_policy` is a verification failure.

For genuine pre-barrier historical worker bytes, absence is represented explicitly as:

`provider_effect_policy:UNAVAILABLE_LEGACY`

rather than being invented retroactively.

## Why the ordinary envelope hash is insufficient

An attacker who can rewrite a JSON file can also recompute an unkeyed envelope SHA-256. The verifier therefore checks policy semantics independently. The adversarial test rewrites a read-only result to claim side-effect blocking, recomputes the outer envelope, and still expects verifier rejection.

## Remaining implementation boundary

This barrier prevents silent side-effect enablement. It does not implement side effects.

Before side-effecting capabilities are enabled, `frost-effect/1.0` (or a superseding reviewed contract) must provide durable states sufficient to distinguish at least:

- intent staged;
- authorized;
- claimed;
- execution started;
- executed;
- result staged;
- independently verified;
- published;
- acknowledged;
- retryable/terminal failure.

The protocol must also define idempotency and crash recovery for the external side effect itself.
