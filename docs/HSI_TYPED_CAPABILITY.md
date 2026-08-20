# HSI typed-capability ingress candidate

This additive adapter maps the hidden-system-identification protocol namespace onto the
existing `frost-call/1.0` proposal-only gateway.

Supported operations:

- `hsi.status`
- `hsi.identify`
- `hsi.run`
- `hsi.verify`
- `hsi.export`

The adapter does not execute them. It creates the same authorization-required canonical
task used by existing frost-call requests. The capability registry remains authoritative.

Security properties:

- no wildcard operation;
- no arbitrary shell/argv/script/package fields;
- immutable SHA-256 references required for specs and verification/export artifacts;
- bounded run count;
- explicit backend names;
- deterministic canonical JSON normalization;
- idempotency key preserved through frost-call;
- no authorization or promotion authority introduced.

The intended execution chain remains:

`HSI request -> frost-call normalization -> CanonicalAdapterGateway -> authorization -> registered capability -> bounded execution -> independent verification -> evidence -> terminal state`
