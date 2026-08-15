# Callable Fabric Independent Result Verification

Status: implementation candidate on `agent/callable-independent-verifier`

## Invariant

A worker-produced result is not eligible for durable publication merely because the worker exited successfully.

The connected GitHub path becomes:

`immutable request -> worker execution -> result staging -> independent verifier -> immutable result + immutable verification -> reconciliation/publish`

The verifier is a separate program and does not import `worker.js` or the semantic fabric's hashing helpers.

## Verification checks

For each request/result pair, the verifier independently checks:

1. `frost-call/1.0` protocol and GitHub provider identity;
2. canonical request SHA-256;
3. idempotency key when available;
4. full result envelope SHA-256;
5. semantic provenance receipt hash;
6. successful semantic result hash against both diagnostics and receipt;
7. source-attestation scope consistency;
8. historical semantic-core, worker, and workflow bytes using fixed `git show <provider_sha>:<path>` reads;
9. composite provider-code identity.

The verifier writes `frost-independent-verification/1.0` records under `runtime/verifications/`.

## Historical source verification

A reconciled duplicate preserves the original execution's `provider_sha` and source attestation. The verifier therefore does not compare the result against whatever worker happens to be current today. It reads the execution-critical files from the historical Git commit named in the result and hashes those bytes.

This permits valid old results to remain verifiable after later provider upgrades.

## Legacy evidence

Historical results created before idempotency keys or source attestation existed are not rewritten.

If their request identity, envelope, receipt, and result hash verify but newer provenance fields are unavailable, the verifier emits:

`VERIFIED_LEGACY_LIMITED`

with explicit checks such as:

- `idempotency_key:UNAVAILABLE_LEGACY`
- `source_attestation:UNAVAILABLE_LEGACY`

This is weaker than full verification and is represented as such.

## Fail-closed publication

For a newly executed request, the worker writes the result only into the Actions workspace. The independent verifier must succeed before the workflow stages `runtime/results/` and `runtime/verifications/` for commit.

A verifier failure exits the job before Git publication. A later recovery sweep can retry the immutable request.

## Backfill without re-execution

If an immutable result already exists but its verification record does not, the worker workflow runs only the independent verifier. It does not invoke the semantic operation again.

This allows existing runtime evidence to acquire explicit verification records without changing result bytes.

## Adversarial CI

`verifier-doctor.js` checks:

- valid fully attested result -> `VERIFIED`;
- modified result with stale envelope -> rejected;
- valid legacy-style result -> `VERIFIED_LEGACY_LIMITED`.

## Remaining boundary

The verifier establishes integrity and provenance of the result record and historical execution code. It does not by itself make arbitrary external side effects transactionally exactly-once. Side-effecting capabilities still require durable execution intent / acknowledgement or provider-native idempotency before enablement.
