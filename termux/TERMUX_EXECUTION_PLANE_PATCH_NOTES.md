# Automation program integration patch

The persistent Termux daemon is a device-side execution capability of the existing Centinal26 autopilot. It must not create a competing planner, policy authority, canonical state database, release authority, or verifier authority.

Autopilot integration contract:

1. GitHub remains durable source authority for repository state, CI, issues, pull requests, and release evidence.
2. The canonical autopilot plans and authorizes operations.
3. Approved device operations are serialized into the Termux daemon queue with stable intent, capability, source revision, payload hash, and idempotency key.
4. The daemon performs bounded execution through registered adapters only.
5. Daemon-local verification is a postcondition check, not independent physical certification.
6. Independent verifier evidence is required before lifecycle promotion to `device-tested`.
7. Failures remain local to the affected capability when possible; independent queued work continues.
8. The Addendum Controller ingests daemon execution/evidence records and records only evidence-supported lifecycle transitions.
9. Scheduler/capacity exhaustion is recoverable by consolidation and checkpointing; it is not permission to fabricate execution continuity.
10. Secrets remain outside GitHub history and evidence payloads.
