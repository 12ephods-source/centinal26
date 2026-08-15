# frost-call/1.0 canonical ingress

## Status

`frost-call/1.0` is a C05 interoperability protocol. Centinal26 remains the canonical
Automation OS state, authorization, execution, verification, and evidence kernel.

The adapter in `src/centinal26/frost_call_adapter.py` is intentionally ingress-only.
It converts a validated frost-call request into `CanonicalAdapterGateway`; it does not
create grants, execute capabilities, mutate release state, or provide a general-purpose
shell.

## Ownership

- C01 Frost Core owns canonical serialization/hash/runtime primitives.
- C02 Guardian owns authorization, capability policy, and fail-closed behavior.
- C03 Provenance & Recovery owns receipts, content hashes, audit/evidence, and rollback data.
- C04 Epistemic Guard owns postcondition, promotion, regression, and validation-state gates.
- C05 Frost Agent Fabric owns frost-call, HTTP/MCP/Base44/Hermes adapters, capability
  negotiation, and provider bindings.

This split prevents the standalone bridge from becoming a competing system of record.

## Request contract

Canonical ingestion accepts only `operation = "intent.submit"`:

```json
{
  "protocol_version": "frost-call/1.0",
  "request_id": "req-123",
  "operation": "intent.submit",
  "idempotency_key": "stable-operation-key",
  "parameters": {
    "capability": "system.echo",
    "payload": {"message": "hello"},
    "constraints": {"max_runtime_seconds": 30},
    "objective": "optional human-readable objective",
    "source": {"transport": "mcp"}
  },
  "caller": {"type": "agent", "id": "caller-id"},
  "provenance": {"upstream": "receipt-or-context"}
}
```

`request_id` is correlation identity. `idempotency_key` is canonical transport identity;
if omitted it defaults to `request_id`. Reusing an idempotency key with different immutable
content fails closed through the existing adapter conflict gate.

The adapter reserves `parameters.constraints._frost_call` and injects protocol, caller,
source, and provenance metadata there so transport provenance survives canonicalization.
Callers cannot supply that reserved field.

## Execution path

```text
HTTP / MCP / Base44 / Hermes / other compatible front end
                         |
                         v
                   frost-call/1.0
                         |
                         v
             frost_call_adapter.py
                         |
                         v
             CanonicalAdapterGateway
                         |
                         v
     SOURCE_INGESTED -> TASK_CREATED
                         |
                         v
               explicit authorization
                         |
                         v
            registered capability only
                         |
                         v
              bounded execution
                         |
                         v
          verification + evidence/audit
                         |
                         v
               canonical state update
```

A frost-call envelope is therefore a proposal, never an authorization grant.

## Compatibility with the standalone bridge lineage

The conversation-produced Frost Callable Fabric v1.1.1 remains useful as a transport
reference and deployable front end. Its release ZIP identity is:

`c6e32043fb5cc625accb52e5f56469bee24dd95bdc6a710e867c76657e9f8951`

The full conversation archive identity is:

`95f364ac4975f118473106b68967739d2721a42dac54c969b3d9dcfb122c003c`

Those hashes establish artifact identity only. The artifacts do not replace Centinal26's
canonical event state, authorization, capability registry, verification, or release
control.

## Deliberate limits

- `model.invoke`, `agent.invoke`, artifact operations, and diagnostics are not direct
  canonical-ingress operations in this adapter. They must be expressed as an authorized
  semantic capability request after `intent.submit`, or remain local to a front-end service
  where they do not mutate canonical Automation state.
- Unknown protocol versions and operations fail before event-state mutation.
- Caller-supplied authorization/grant-looking fields carry no authority.
- Unregistered capabilities such as `shell.exec` remain non-executable even when the
  surrounding task is explicitly authorized.
- Host validation does not imply Android/Termux device validation.
