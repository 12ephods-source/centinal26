# Canonical ChatGPT Export Bridge

## Status

`conversation.import_chatgpt_export` is a bounded Centinal26 capability for deriving a local,
hash-verifiable Markdown conversation corpus from an already preserved ChatGPT provider export.
It is not an export acquisition mechanism and it does not grant itself execution authority.

## Canonical execution path

```text
frost-call/1.0 intent.submit
  -> CanonicalAdapterGateway
  -> SOURCE_INGESTED
  -> TASK_CREATED / READY
  -> explicit `centinal26 advance --authorize`
  -> registered `conversation.import_chatgpt_export` capability
  -> immutable export receipt re-verification
  -> bounded transcript derivation
  -> independent transcript/manifest/source re-hash
  -> execution evidence
  -> verified runtime result
  -> canonical task completion and reduced capability state
```

The existing gateway remains proposal-only. The bridge becomes executable only after the normal
Centinal26 advance path finds the registered capability, confirms that its verifier is marked
independent, and receives explicit authorization.

## Input contract

The capability payload is intentionally restricted to exactly:

```json
{"receipt_id":"<64 lowercase hexadecimal characters>"}
```

No provider export path, output destination, executable path, shell command, API credential, or
evidence-root override is accepted from the task payload. The evidence root is local configuration
(`CENTINAL26_EXPORT_EVIDENCE_ROOT`) and the derived destination is fixed beneath the Centinal26
state home as `chat-imports/<receipt_id>`.

Before import, `verify_receipt` independently re-hashes the content-addressed raw export object.
A missing, malformed, conflicting, or tampered receipt/object fails closed.

## Conversation branch semantics

When an exported conversation contains `current_node` and parent links, the bridge reconstructs the
selected branch by walking from `current_node` to the root and reversing that path. Sibling response
branches are not timestamp-merged into the selected transcript. For older or malformed export
shapes that do not expose a usable selected path, the bridge falls back to deterministic timestamp
ordering and therefore does not claim branch-selection fidelity for that conversation.

## Derived artifacts

For each imported conversation the bridge writes one Markdown transcript and records its SHA-256 in
`chatgpt-import-manifest.json`. The manifest also binds:

- provider-export receipt ID;
- raw export SHA-256 and byte size;
- conversation and message counts;
- transcript relative paths and SHA-256 values.

The independent verifier re-verifies the provider receipt, the manifest hash, path confinement,
conversation/message counts, and every transcript hash. Only after that verification does the
AutomatedEngine permit its reducer to update canonical capability state.

## Evidence boundary

The verified facts are limited to stored-byte identity, receipt binding, deterministic derivation,
and derived-artifact integrity. This capability does **not** prove that a provider export is
complete, that every record in it is true, that a particular person authored a message, or that the
content establishes attribution or authorization. Those are separate evidence questions.

Host tests do not establish Android/Termux execution or reboot persistence. Device promotion remains
subject to the existing physical qualification gates.
