# Canonical Adapter Gateway

Status: integration candidate on current canonical `main`; canonical only after repository gates pass and merge.

## Purpose

External systems may propose work, but none of them owns Automation OS state or execution
authority. Base44, Discord, HERMES, AAARD, and FRAS normalize incoming records through one
gateway into the existing Centinal26 event-sourced task graph.

The canonical ingress path is:

`external adapter record -> SOURCE_INGESTED -> TASK_CREATED`

Execution remains the existing path:

`TASK_CREATED -> explicit authorization -> registered capability -> bounded execution -> independent verification -> evidence -> terminal task event`

The adapter gateway does not create grants, execute capabilities, or mark work verified.

## Stable identity and idempotency

Each adapter request is identified by the pair:

`adapter_id + external_id`

The event entities are deterministic from that stable pair. The immutable request content is
canonical-JSON hashed with SHA-256.

- same adapter/external ID + same content: idempotent replay, no new event;
- same adapter/external ID + different content: fail-closed `AdapterRequestConflict`;
- crash after `SOURCE_INGESTED` but before `TASK_CREATED`: the next ingestion resumes by
  creating only the missing task.

This separates transport retry behavior from task duplication.

## Authority boundary

Catalog membership is descriptive, not authorization. `intent.submit` means an adapter may
submit a proposal into canonical state; it does not mean its provider is connected, validated,
or allowed to execute.

Incoming payload fields such as `authorize`, `approved`, or `grant` have no authority. They
remain ordinary task input. Actual execution still requires Centinal26's explicit authorization
gate and a registered capability with an independent verifier.

An adapter request for `shell.exec`, for example, becomes a canonical task but remains blocked
as `NO_CAPABILITY` because the default advance runtime does not expose an arbitrary shell
capability.

## Adapter surfaces

The canonical ingress set is deliberately explicit:

- `base44` — control-plane/rendezvous adapter;
- `discord` — messaging transport;
- `hermes` — agent/orchestration adapter;
- `aaard` — legacy/domain control-plane adapter;
- `fras` — scientific/research adjudication adapter.

All five expose `intent.submit` in the federation catalog. Their catalog status does not
silently advance as a consequence of this gateway.

For FRAS specifically, submitting a research claim or solver task is not scientific
validation. It merely places the task behind the same authorization, execution, verification,
evidence, and state-transition gates as other Automation OS work.

## Existing convergence reused

This gateway intentionally reuses rather than replaces existing merged components:

- the append-only SHA-256 event store and deterministic replay;
- deterministic universal ingestion;
- bounded `advance --until-idle`;
- auxiliary durable execution queue/evidence store;
- `frost-effect/1.0` for consequential provider effects;
- control-plane reconciliation;
- acknowledged condition-watch delivery outbox.

The event log remains the operational source of truth for canonical tasks. Provider queues,
Base44 records, Discord messages, HERMES plans, AAARD records, and FRAS records are inputs or
mirrors, not parallel authorities.

## Validation target

The host test contract covers:

1. each supported adapter produces exactly one canonical source and task;
2. retries are idempotent;
3. content conflicts fail closed;
4. adapter payloads cannot self-authorize execution;
5. unregistered capabilities cannot execute;
6. event replay reproduces the same canonical state.

Physical Android/Termux execution is a separate evidence gate. Host tests do not promote
device-validation status.

© 2026 Robert Frost
