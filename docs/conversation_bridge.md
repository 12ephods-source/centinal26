# Conversation → Responder → Termux Loop

Status: implementation candidate for Centinal26 / Frost CORE.

## Purpose

Provide one durable path for an AI conversation turn to reach a configured AI responder, allow that responder to request strictly local Termux capabilities, feed each capability result back to the responder, persist the final response, return it through the Base44 control plane, and continue polling for later turns without manual copy/paste.

## Runtime path

```text
conversation.ingest frost-call job
  -> Base44 worker on Termux
  -> frost_core.conversation_cli
  -> ConversationLoop
  -> responder adapter
  -> registered capability request (optional)
  -> SHA-256-pinned local script, shell=False
  -> structured function_call_output
  -> same responder conversation
  -> repeat until final text / budget stop
  -> local SQLite state
  -> AutomationResult + AutomationJob completion
```

`conversation.status` follows the same transport but performs no model call.

## Shared/provider split

Shared Frost CORE:

- `conversation_loop.py`: durable request/session state, loop budgets, model/tool feedback, ingress idempotency.
- `capability_executor.py`: local capability registration, SHA-256 pinning, argument/output/time bounds, scrubbed execution environment, call-id deduplication.

Provider adapters:

- `openai_responder.py`: OpenAI Responses API translation only.
- `base44_conversation_worker.mjs`: Base44 polling/lease/result/audit translation only.
- `install_conversation_bridge.sh`: Android/Termux deployment and boot wiring only.

The shared loop does not depend on Base44 or OpenAI.

## Safety invariants

1. There is no remote shell operation.
2. A model can invoke only a locally registered capability name.
3. The executable path is chosen locally at registration time and pinned by SHA-256.
4. Every invocation rechecks the executable hash before running it.
5. Execution uses an argv vector with `shell=False` and bounded string arguments.
6. Model/provider credentials are stripped from capability subprocess environments.
7. Capability call IDs are idempotent locally: a repeated call ID returns the stored result rather than rerunning the script.
8. A request ID cannot be reused for different conversation content.
9. Loop steps, tool calls, wall time, argument sizes, output sizes, and script timeouts are bounded.
10. AI-generated final text is returned as an unverified model output. Completing a conversation job does not promote that text to independently verified evidence.

## Base44 job contract

Create a normal `AutomationJob` using the already registered `frost-call/1.0` operation:

```json
{
  "job_type": "frost_call",
  "status": "queued",
  "worker_email": "WORKER_ACCOUNT",
  "parameters_json": "{}",
  "payload_json": "{\"conversation_id\":\"my-session\",\"content\":\"Check the local runtime and tell me what you find.\"}",
  "requested_at": "ISO-8601 timestamp",
  "request_nonce": "unique nonce",
  "protocol_version": "frost-call/1.0",
  "request_id": "unique stable request ID",
  "operation": "conversation.ingest",
  "idempotency_key": "unique stable request ID",
  "timeout_seconds": 960,
  "risk_class": "LOW"
}
```

Use the same `conversation_id` for later human turns. Each turn must use a new `request_id`. Within each turn, responder → Termux → responder feedback cycles run automatically.

## Installation

From the implementation branch/source checkout on the Android device:

```bash
bash termux/install_conversation_bridge.sh
```

The installer creates a dedicated venv and Node runtime directory, asks once for Base44 and responder credentials when they are not already supplied by environment variables, installs two read-only default capabilities (`termux.system_status` and `centinal26.status`), starts the worker, and installs a Termux:Boot launcher.

Control commands:

```bash
frost-conversation-bridge-status
frost-conversation-bridge-stop
frost-conversation-bridge-start
```

Register another local script as a capability:

```bash
frost-conversation-register \
  --name my.safe.check \
  --script /absolute/path/to/check.sh \
  --description "Read-only check used by the responder" \
  --max-args 2 \
  --timeout 30
```

Registration is local administrative configuration. The remote conversation cannot add or modify capability registrations.

## Validation boundary

The unit suite validates the provider-neutral feedback loop, cached ingress behavior, local call-id deduplication, hash-drift denial, and response parsing. A real Android/Termux run is still required before the implementation can be labeled DEVICE_VALIDATED or PERSISTENT_VALIDATED.
