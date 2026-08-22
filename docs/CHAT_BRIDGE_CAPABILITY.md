# Canonical ChatGPT Export Bridge

## Status

`conversation.import_chatgpt_export` is a bounded Centinal26 capability for deriving a local, hash-verifiable Markdown conversation corpus from an already preserved ChatGPT provider export. It is not an export acquisition mechanism and it does not grant itself execution authority.

## Canonical execution path

```text
frost-call/1.0 intent.submit
  -> CanonicalAdapterGateway
  -> SOURCE_INGESTED
  -> TASK_CREATED / derived readiness
  -> explicit `centinal26 advance --authorize`
  -> registered `conversation.import_chatgpt_export` capability
  -> immutable export receipt re-verification
  -> bounded transcript derivation
  -> independent transcript/manifest/source re-hash
  -> execution evidence
  -> verified runtime result
  -> canonical task completion and reduced capability state
```

## Input contract

The capability payload is restricted to exactly:

```json
{"receipt_id":"<64 lowercase hexadecimal characters>"}
```

No provider export path, output destination, executable path, shell command, API credential, or evidence-root override is accepted from the task payload. The evidence root is local configuration (`CENTINAL26_EXPORT_EVIDENCE_ROOT`) and the derived destination is fixed beneath the Centinal26 state home as `chat-imports/<receipt_id>`.

Before import, `verify_receipt` independently re-hashes the content-addressed raw export object. A missing, malformed, conflicting, or tampered receipt/object fails closed.

## Conversation branch semantics

When an exported conversation contains `current_node` and parent links, the bridge reconstructs the selected branch by walking from `current_node` to the root and reversing that path. Sibling response branches are not timestamp-merged into the selected transcript. Older or malformed export shapes without a usable selected path fall back to deterministic timestamp ordering; branch-selection fidelity is not claimed for that fallback case.

## Derived artifacts and independent verification

For each imported conversation the bridge writes one Markdown transcript and records its SHA-256 in `chatgpt-import-manifest.json`. The manifest binds the provider-export receipt ID, raw export SHA-256 and byte size, conversation/message counts, relative transcript paths, and transcript SHA-256 values.

The independent verifier re-verifies the provider receipt, manifest hash, path confinement, counts, and every transcript hash. Only after that verification may the `AutomatedEngine` reducer update capability state.

## Evidence boundary

Verified facts are limited to stored-byte identity, receipt binding, deterministic derivation, and derived-artifact integrity. This capability does not prove provider-export completeness, message truth, authorship, attribution, or authorization represented inside the export.

Host tests do not establish Android/Termux execution or reboot persistence. Device promotion remains subject to the physical qualification gates.
