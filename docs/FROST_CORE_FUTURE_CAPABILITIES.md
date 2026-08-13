# Frost CORE Ω — Enabled Future Capabilities

Frost CORE Ω is the future-capability horizon for Automation OS. This document marks the
first subset that is implemented as executable, host-safe decision logic rather than only a
conceptual target.

These modules do not receive independent authority. They feed the canonical Automation OS
invariant:

`Intent -> Authorization -> Event/Queue -> Capability Selection -> Bounded Execution -> Verification -> Evidence/Audit -> State Update -> Controlled Evolution`

## Enabled experimental capabilities

### Intelligence Awareness

Operational epistemic awareness over explicit evidence classes:

- `OBSERVED`
- `EXPLICIT`
- `DERIVED`
- `INFERRED`
- `SPECULATIVE`
- `UNKNOWN`

The module calculates support, uncertainty, contradiction pressure, evidence coverage, and a
trust score. It distinguishes `SUPPORTED`, `INCOMPLETE`, `CONTESTED`, and `UNKNOWN` states.
It is not a claim of consciousness or philosophical self-awareness.

### Predictive Attention

Machine attention management evaluates expected consequences rather than emitting every signal
as a notification. Signals are scored using urgency, impact, confidence, novelty,
irreversibility, deadline pressure, and interruption cost.

Possible actions are:

- `INTERRUPT`
- `DELEGATE`
- `QUEUE`
- `SUPPRESS`
- `REQUEST_EVIDENCE`

A high-impact signal with inadequate confidence requests evidence before action. Low-value noise
is suppressible. This implements the target of predictive attention rather than notification
spam.

### Delegated Cognition

The router selects the lowest-human-attention path that still preserves authorization and risk
boundaries:

- `BOUNDED_AGENT`
- `MULTI_AGENT_REVIEW`
- `HUMAN_REVIEW`
- `DEFER`

No unauthorized task may be routed to an autonomous agent. High-risk or highly irreversible
work remains human-reviewed.

### Strategic Branch Forecasting

Bounded candidate branches can be ranked by immediate expected value, exploration value, and
future optionality. This allows the system to preserve branches that may be less attractive
immediately but create a better future search space.

Forecasting is advisory. It cannot merge, release, promote, weaken a validator, or change its
own evaluator.

## Still gated

### Adversarial candidate execution

Status: `GATED`.

Issue #18 remains the hard gate. Static analysis and a Git worktree are not a security sandbox.
Execution of genuinely adversarial candidates requires a hard isolated evaluator with network
default-deny, secret isolation, resource bounds, and fail-closed sandbox creation.

### Physical-device autonomy

Status: `GATED`.

Requires real Android/Termux device validation, persistence validation, and verified audit
evidence. Host execution cannot satisfy these requirements.

### Autonomous promotion to main

Status: `DISABLED`.

Explicit human promotion remains a canonical control boundary. Future cognition modules may
recommend, rank, test, and preserve candidates; they may not silently convert recommendation
into production authority.

## Maturity meaning

`ENABLED_EXPERIMENTAL` means executable host-safe decision logic with regression tests. It does
not mean physical-device validation, autonomous production authority, or GA release status.

`GATED` means the interface/requirement is represented but execution remains blocked until its
named empirical/security prerequisites exist.

`DISABLED` means the behavior is intentionally outside the present autonomy boundary.
