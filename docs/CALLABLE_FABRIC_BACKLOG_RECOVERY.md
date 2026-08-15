# GitHub Callable Fabric — Backlog and Provider-Outage Recovery

Status: implementation candidate on `agent/github-callable-backlog-recovery`

## Problem

The connected GitHub Actions worker originally woke only when a new request file was pushed to `callable-runtime`. If Actions or a provider run failed after that push, pending immutable requests could remain in the repository without any future event that would retry them.

## Recovery model

The worker now has three wake-up paths:

1. request-path push on `callable-runtime`;
2. explicit `workflow_dispatch` operator recovery;
3. an hourly scheduled backlog sweep at minute 17.

All triggers explicitly check out `callable-runtime`. Scheduled workflows originate from the default branch, so the fixed checkout ref is required to avoid accidentally sweeping `main` instead of the execution queue.

## Serialization and bounds

All worker events share the static concurrency group:

`frost-callable-fabric-callable-runtime`

`cancel-in-progress: false` preserves queued recovery work instead of cancelling an in-flight worker. Each job has a 20-minute timeout.

## Result reconciliation

After producing immutable result files, the worker commits locally and then performs up to three bounded fetch/rebase/push attempts against `origin/callable-runtime`. This handles the normal race in which another authenticated request is appended while the worker is executing.

Failure after three attempts remains a visible workflow failure. The next push, manual dispatch, or scheduled sweep can recover any request whose immutable result was not published.

## Idempotency interaction

The connected worker already reconciles a request by `idempotency_key` plus canonical request hash when a verified durable result exists. A scheduled sweep therefore does not intentionally re-execute requests that already have immutable result evidence.

## Remaining crash boundary

This change does not claim transactional exactly-once external side effects across a runner crash after an operation executes but before its result becomes durable in Git. The currently connected capability set remains semantic/read-only, so replay is bounded to read-only semantic work.

Before a side-effecting capability is enabled on this provider, it must supply provider-native idempotency or a durable execution-intent/acknowledgement protocol that can distinguish:

- not started;
- started;
- executed;
- result staged;
- verified;
- published;
- acknowledged.

## Cost posture

The recovery sweep runs hourly rather than at a high polling rate. Event-driven request pushes remain the normal fast path; the schedule is a bounded safety net for missed or failed runs.
