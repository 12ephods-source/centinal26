# Automation OS Architecture

## Purpose

Automation OS is a layered automation platform that unifies earlier AI brain, agent platform, Sentinel/Guardian, AAARD/AICCEP-OS, async supervisor, queue, evidence, and controlled-evolution work under one execution model.

## Canonical execution path

1. **Intent** — a requested goal is represented explicitly.
2. **Authorization** — authority, scope, risk, and constraints are resolved before consequential work.
3. **Event/Queue** — accepted work becomes a durable event/job rather than an implicit side effect.
4. **Capability Selection** — an allowlisted capability and executor are selected.
5. **Bounded Execution** — execution is constrained by arguments, environment, resources, timeout, and policy.
6. **Verification** — declared postconditions are checked independently of the executor when practical.
7. **Evidence/Audit** — inputs, outputs, hashes, errors, provenance, and decisions are preserved.
8. **State Update** — durable state changes only after verification outcome is known.
9. **Controlled Evolution** — improvements are proposed from evidence and must pass the same gates before becoming canonical.

## Layers

### Control plane
Intent normalization, authorization, queueing, leases, capability registry, policy, state transitions.

### Execution plane
Termux/Hermes/local workers execute named capabilities. Workers do not accept unrestricted shell payloads from remote requesters.

### Evidence plane
Immutable or append-oriented records preserve job envelopes, capability versions, input/output hashes, verification results, failures, and environment metadata.

### Knowledge/continuity plane
AICCEP-OS-style knowledge, project state, provenance, conflicts, and canonical object-store functions maintain continuity across conversations and artifacts.

### Application/agent plane
AAARD and specialized agents consume the control plane rather than bypassing it.

## Status taxonomy

- `CANONICAL`: authoritative current implementation or specification.
- `COMPATIBLE_MODULE`: valid module that conforms to canonical invariants.
- `EXPERIMENTAL`: promising but not release-authoritative.
- `SUPERSEDED`: retained for provenance but replaced.
- `REJECTED`: known-invalid or intentionally excluded.

## Validation levels

Validation claims must identify their environment. Suggested levels:

- `STATIC_VALIDATED` — syntax/schema/static checks only.
- `HOST_VALIDATED` — executed successfully in a non-target host environment.
- `DEVICE_VALIDATED` — executed on the intended Android/Termux target.
- `ENDURANCE_VALIDATED` — repeated/restart/recovery behavior exercised on target.
- `RELEASE_VALIDATED` — all release gates satisfied for declared scope.

A higher-level claim must not be inferred from a lower-level one.
