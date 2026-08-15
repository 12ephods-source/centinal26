# Remaining feature execution — 2026-08-14

This document records what the consolidated host implementation closes and what remains
an empirical/external boundary. It deliberately separates **implemented source** from
**connected/device evidence**.

## Implemented in this batch

### Consequential execution substrate

- `frost-effect/1.0` durable request/authorization/claim/execution/verification/
  publication/acknowledgement ledger.
- crash after persisted execution intent becomes `RECOVERY_REQUIRED`, never automatic
  blind retry.
- request and provider idempotency identities.
- independent verifier requirement.
- SHA-256 hash-linked effect transition history.

### Provider-neutral routing

- durable provider registry;
- explicit maturity and availability states;
- capability, latency, cost, source-identity, type, and maturity filters;
- explicit routing policy on every selection;
- no implicit universal provider default.

### Capability Factory

- durable `DISCOVERED -> WRAPPED -> BUILDABLE -> TESTED -> DEPLOYED -> REACHABLE ->
  CHATGPT_CALLABLE_VERIFIED -> PROMOTED` control;
- mandatory promotion gates;
- regression demotion;
- source mismatch quarantine;
- unrestricted remote-shell candidates rejected.

### Control-plane reconciliation

- desired vs observed mirror diff;
- immutable execution-evidence identity required;
- post-write readback;
- divergence state rather than assumed success;
- suitable for Base44 or another replaceable control plane without making it the
  immutable source of execution truth.

### Provenance archaeology

- bounded read-only file and nested-ZIP hashing/search;
- exact SHA-256 match classification;
- filename/text leads;
- traversal rejection;
- member/depth/byte bounds;
- no extraction execution.

### Software/App Creation boundary

- typed v0 operation set;
- local request idempotency;
- response hashing;
- deterministic `prepare_pr` synchronization object;
- `github_write_authorized=false` by construction so app generation cannot silently gain
  repository mutation authority.

### SDOS branch ledger

- immutable theory branch identity;
- assumptions/parameters/observable map/implementation/falsification criteria;
- independently verified experiment evidence;
- explicit branch statuses;
- rejected and incompatible branches remain in history.

### HERMES federation catalog

Typed descriptors now cover the planned cloud-model, local-model, agent-framework,
protocol, messaging, execution-provider, control-plane, and app-generation adapters.
Catalog membership is not authorization or connectivity. Unconfigured adapters stay
`NOT_CONFIGURED`.

## Still blocked on real external/device evidence

- actual Cloudflare R2 Terraform apply and live custom-domain verification;
- Cloudflare WAF/Access policy content and account-side validation;
- physical Android/Termux C3/C4 execution, reboot persistence, endurance, device sync,
  recovery drill, and native certification;
- RC4/GA promotion;
- real side-effect provider adapters promoted onto `frost-effect/1.0`;
- hard sandbox for hostile candidate execution;
- actual v0 service connectivity;
- broad cloud/local HERMES adapters beyond catalog normalization;
- live NATS/MQTT/ZeroMQ/Matrix/WebSocket/A2A connections;
- YouTube transcriber real device-network validation;
- empirical Dragon Evolution candidate promotion;
- large-scale endurance/chaos certification rather than focused host regression tests.

These remain open by evidence, not by wording. Host tests cannot close them.
