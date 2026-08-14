# Frost Automation OS Ω / Centinal26 — Final Host Specification

Status: **HOST_COMPLETE / EXTERNAL_CERTIFICATION_PENDING**
Date: 2026-08-14
Canonical repository boundary: `12ephods-source/centinal26@19acce745575ee719bf429d82b00761ce67e84f1`

## 1. System purpose

Frost Automation OS Ω is a local-first, evidence-centered automation substrate for durable agents, scientific and security plugins, provider-neutral callable capabilities, Android/Termux execution, project continuity, and controlled evolution.

Centinal26 is the canonical implementation/release line. Frost CORE / Frost Callable Fabric owns the reusable execution and capability machinery. AICCEP-OS / Canonical Object Store owns authoritative project knowledge and provenance. AAARD and domain systems are applications/plugins, not the execution authority.

## 2. Constitutional execution pipeline

`Intent → Authorization / Guardian → Durable Queue → Capability Selection → Bounded Execution → EXECUTED → Independent Verification → Evidence / Audit → State Update → Controlled Evolution`

The pipeline is fail-closed. Provider adapters may narrow behavior but cannot bypass policy, replay protection, verification, audit, or promotion gates.

## 3. Final shared implementation

The `frost_exec` shared package is version 1.0.0 for the host-complete release. It includes:

- canonical JSON and SHA-256 identity;
- fsync/atomic writes;
- immutable content-addressed storage;
- unified immutable canonical object store with provenance, relationships and alias history;
- durable SQLite queue with idempotency keys;
- leases, heartbeats, stale-lease recovery and bounded retry;
- bounded asynchronous supervisor;
- allowlisted subprocess execution with scrubbed environment, timeout and output caps;
- explicit `EXECUTED` vs `VERIFIED` separation;
- typed independent verifier contract;
- HMAC-authenticated request envelopes with expiry and replay prevention;
- append-only hash-linked audit chain;
- CI completion reduction;
- exactly-once terminal condition-watch ledger;
- single-instance lock.

## 4. State and evidence classes

Execution jobs: `SUBMITTED/QUEUED → RUNNING → PASS | REVIEW | FAIL | ERROR`.

- `ERROR` is infrastructure failure and may be retried within policy.
- `FAIL` is an evaluated failure and is preserved; it is not silently retargeted.
- Capability execution additionally records `EXECUTED` before independent verification.

Artifact/project classifications: `CANONICAL`, `COMPATIBLE_MODULE`, `EXPERIMENTAL`, `SUPERSEDED`, `REJECTED`, plus explicit provenance labels for reconstructed/recovered content.

## 5. Provider adapters

Base44, Discord/FAIR, Vercel, GitHub, MCP/HTTP, Termux/Hermes and model providers are adapters. Credentials and live deployment IDs are runtime state, never shared-policy constants.

## 6. Controlled evolution

Evolution is subordinate to Guardian/MetaPolicy. It may propose candidates and derive stricter constraints, but cannot widen authorization, erase failed evidence, bypass rollback, certify physical execution, or self-promote.

## 7. Conversation/project continuity

The normalized corpus contains every Automation conversation group recoverable from the current project context, canonical conversation bundle, File Library recoveries and project history. Each record is content-addressed in `automation_conversation_corpus.sqlite3`. Raw transcript completeness is not claimed where a complete project export was unavailable.

## 8. Completion definition

The host software project is complete when all deterministic host gates pass and the remaining items require evidence from an external execution environment rather than missing host code. This release meets that definition.

External certification remains separately gated for physical Android/Termux behavior, fresh durable Base44 worker autonomy, live current Vercel/provider reachability, and any future complete raw ChatGPT export ingestion.
