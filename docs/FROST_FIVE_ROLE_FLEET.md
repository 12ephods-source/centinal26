# Frost Five-Role Fleet Runtime

## Purpose

The Frost fleet turns the staggered hourly Governor → Builder → Judge → SRE → Evolution workflow into one durable coordination protocol rather than five independent prompt memories.

The runtime is deliberately split into two layers:

- **Centinal26/Frost CORE SQLite** is the provider-neutral local reference ledger and deterministic protocol implementation.
- **Base44 Superagent** mirrors cross-agent contracts, results, verdicts, handoffs, metrics, and error-budget events so scheduled ChatGPT roles and external adapters can coordinate against the same durable identities.

Neither layer grants execution authority. Guardian/policy and the bounded worker/capability system remain authoritative for consequential execution.

## Roles and cadence

The intended staggered fleet is:

| Minute | Role | Responsibility |
|---|---|---|
| `:00` | Governor | Reconcile state, discover/rank problems, issue deduplicated contracts |
| `:10` | Builder | Implement/repair up to three independent bounded contracts |
| `:25` | Judge | Independently falsify/verify immutable results |
| `:40` | SRE | Operate, recover, roll back, and establish physical/runtime truth |
| `:50` | Evolution | Run bounded candidate tournaments and optimization searches |

The cadence is an orchestration convenience, not a claim that every event should wait for the next scheduled role. Existing event-sensitive mechanisms may surface urgent state sooner. The fleet ledger prevents those triggers from creating incompatible memories.

## Contract lifecycle

A work contract contains immutable intent plus mutable execution state.

Immutable contract intent includes:

- `contract_id` and `contract_hash`
- `idempotency_key`
- problem statement and source basis
- P0–P4 priority and ranking factors
- expected outcome and measurable success criteria
- allowed and prohibited scope
- dependency identities
- assigned role
- verification requirements
- rollback and resource budgets
- retry budget
- source/head identity
- subsystem
- failure criteria and next review condition
- optional `on_verified_role`

Mutable state is stored separately in the SQLite implementation and represented as mutable state fields in the Base44 mirror:

- owner role
- lifecycle status
- claimer
- lease expiry
- attempt count
- terminal reason

Materially changing the immutable intent requires a successor contract; it must not silently rewrite the old evidence.

## Idempotency and deduplication

Base44 does not provide a uniqueness constraint for the fleet records. Every role therefore follows **query before create** semantics.

1. Derive a stable identity/hash from immutable content.
2. Query by `idempotency_key`, `result_id`, `verdict_id`, `handoff_id`, or snapshot/error ID.
3. Reuse the existing record when it already represents the same immutable fact.
4. Create a versioned successor only when new evidence materially reopens a terminal problem.

The local SQLite implementation additionally enforces unique constraints.

## Evidence separation

`fleet_contracts`, `fleet_results`, `fleet_verdicts`, and `fleet_event_log` are append-only in SQLite through triggers. Mutable claim/lifecycle state is stored in separate state tables.

This separation prevents a role from rewriting what it previously claimed to have done or verified.

The Base44 mirror uses admin-only RLS for:

- `AutomationWorkContract`
- `AutomationRoleResult`
- `AutomationVerificationVerdict`
- `AutomationHandoff`
- `AutomationFleetMetric`
- `AutomationErrorBudgetEvent`

Role prompts treat result and verdict records as immutable evidence even though Base44's generic update API exists.

## Handoff protocol

Typical implementation flow:

```text
Governor
  └─ READY / owner=BUILDER
       └─ Builder RUNNING
            └─ AutomationRoleResult(EXECUTED_AWAITING_VERIFICATION)
                 └─ handoff → Judge
                      ├─ VERIFICATION_FAILED → original implementation role
                      └─ VERIFIED
                           ├─ terminal VERIFIED, or
                           └─ handoff → on_verified_role (often SRE or Governor)
```

Evolution candidate packages and consequential SRE evidence follow the same independent-Judge boundary.

A role cannot promote its own consequential result by writing `VERIFIED` into its result payload.

## Ranking

The reference `rank_contract` implementation combines a P0–P4 base with normalized factors:

Positive value:

- downstream leverage
- user impact
- dependency unblocking
- uncertainty reduction
- information gain
- expected success probability
- verification value
- execution readiness

Penalties:

- remaining cost
- maintenance burden
- rollback cost
- risk

The score is a prioritization heuristic, not an authorization score. A high score cannot override a hard policy or validation failure.

## Leases and retries

Role claims are leased. An expired `RUNNING` contract may be reclaimed when:

- its lease has actually expired;
- dependencies remain satisfied;
- its retry budget is not exhausted;
- the subsystem is not mutation-contracted by the error budget.

Retry exhaustion produces preserved failure rather than an infinite loop.

## Error budget and automatic contraction

SRE/Judge record operational failures and invariant violations as `AutomationErrorBudgetEvent` / `fleet_error_events`.

The local reference implementation contracts a subsystem when either:

- an invariant violation exists in the rolling window; or
- repeated failures produce a materially elevated unrecovered failure rate.

While contracted, Builder and Evolution stop taking mutation work in that subsystem. Judge and SRE may continue verification, containment, recovery, and rollback. Re-expansion requires verified corrective evidence.

This is an operational safety brake, not a replacement for Guardian authorization.

## Metrics

Fleet snapshots can preserve:

- total/open/solved/failed/blocked contracts
- solve fraction
- verification count/failure rate
- mean attempts
- duplicate-work rate
- rollback rate
- CI recovery rate
- oldest unresolved P0/P1 age
- event-chain integrity

Metrics should improve routing and eliminate repeated low-yield work. They must not autonomously weaken authority or validation policy.

## CLI

The package exposes:

```bash
centinal26-fleet init
centinal26-fleet status
centinal26-fleet metrics
centinal26-fleet contract --json '{...}'
centinal26-fleet claim BUILDER --claimer frost-builder --batch-limit 3
centinal26-fleet result CONTRACT BUILDER EXECUTED_AWAITING_VERIFICATION --payload '{...}'
centinal26-fleet pending-verification --limit 3
centinal26-fleet verdict RESULT VERIFIED --verifier frost-judge --details '{...}'
centinal26-fleet error provider RECOVERY_FAILURE HIGH --details '{...}'
centinal26-fleet error-budget provider
```

The fleet CLI shares `CENTINAL26_HOME/intelligence.sqlite3` with the existing intelligence controller; the table namespaces do not collide.

## Current release gate

Centinal26 `1.0.0` remains empirically gated by GitHub issue #64. The durable Base44 work contract uses:

```text
idempotency_key = release:centinal26-1.0.0:physical-gate-64:v1
assigned_role   = SRE
on_verified_role = GOVERNOR
```

Physical promotion requires real Android/Termux evidence, including the Node/controller, local work, lease recovery, heartbeat advancement, event-chain validity, fail-closed unsupported-command denial, a genuine reboot and Termux:Boot return, post-reboot work, endurance sampling, watchdog recovery, device-sync binding, and independent verification.

No host, ChatGPT session, GitHub Actions run, simulation, or metadata edit may substitute for that evidence.

## Authority invariant

The fleet's governing invariant remains:

```text
Intelligence proposes.
Policy authorizes.
Containment limits.
Workers execute.
Independent verification confirms.
Evidence and audit preserve what happened.
```

The fleet increases throughput and closure discipline; it does not give any role permission to self-authorize arbitrary execution.
