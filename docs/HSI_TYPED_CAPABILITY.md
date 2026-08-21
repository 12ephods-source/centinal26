# HSI typed-capability ingress

Status: `HOST_CANDIDATE / PROPOSAL_ONLY`

This adapter maps the hidden-system-identification protocol namespace onto the existing `frost-call/1.0` proposal-only gateway.

Supported operations:

- `hsi.status`
- `hsi.identify`
- `hsi.run`
- `hsi.verify`
- `hsi.export`

The adapter does not execute these operations. It creates the same authorization-required canonical proposal used by existing frost-call ingress. The normal capability registry and authorization path remain authoritative.

Security properties:

- no wildcard operation;
- no arbitrary shell, argv, script, executable, or package fields;
- immutable SHA-256 references required for specifications and verification/export artifacts;
- bounded run count;
- allowlisted backend names and objective names;
- deterministic canonical JSON normalization;
- idempotency key preserved through frost-call;
- no new authorization, execution, or promotion authority.

The intended chain remains:

`HSI request -> frost-call normalization -> CanonicalAdapterGateway -> authorization -> registered capability -> bounded execution -> independent verification -> evidence -> terminal state`

This module establishes typed proposal ingress only. If a downstream `hsi.*` capability is not separately registered and authorized, execution must fail closed.
