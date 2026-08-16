# Neutral ChatGPT export evidence store

Status: blocker-remediation / evidence-recovery support. This is not a Wordbook feature and it does not change physical-release authority.

## Purpose

A ChatGPT/OpenAI data export is acquired once, preserved as raw bytes, bound to SHA-256 and provider provenance, and then reused by downstream consumers. Wordbook, conversation recovery, DFIR analysis, or later corpus indexing must consume the preserved object instead of downloading a second copy.

The store intentionally does **not** extract ZIP files during preservation. Raw provider bytes remain separate from any later derived/extracted corpus.

Default root:

`~/.local/share/centinal26/evidence/exports/`

Layout:

- `objects/sha256/<prefix>/<sha256>` — immutable raw content-addressed bytes.
- `receipts/<receipt_id>.json` — immutable provenance receipt.
- `index/receipts.jsonl` — append-only receipt index.
- `.ingest.lock` — local serialization lock for concurrent ingesters.

## Preserve an OpenAI export

After an authorized retrieval step has produced the export file locally:

```bash
python -m centinal26.export_evidence \
  preserve /path/to/chatgpt-export.zip \
  --provider openai-chatgpt \
  --message-id '<gmail/provider message id>' \
  --export-id '<provider export id if available>' \
  --message-date '2026-08-16T10:00:00Z' \
  --subject 'ChatGPT - Your data export is ready' \
  --retrieved-at '2026-08-16T10:01:00Z'
```

`message-id` and `export-id` are optional because some retrieval surfaces may not expose both. When supplied, each becomes a strong provider source identity: the same provider identity is never allowed to bind later to different bytes.

Possible successful statuses:

- `PRESERVED` — new content object and new source receipt.
- `REUSED_OBJECT` — the exact bytes already existed, but this is a new legitimate source receipt.
- `DUPLICATE_SOURCE` — the same source identity/content was already preserved; no duplicate receipt is appended.

A conflicting provider message/export identity produces `SOURCE_IDENTITY_CONFLICT` and fails closed.

## Verify before downstream use

```bash
python -m centinal26.export_evidence verify '<receipt_id>'
```

Verification re-hashes the raw object and checks its byte size. Downstream code should use the returned verified `object_path`; it should not assume a receipt proves current object integrity without this check.

## Evidentiary boundaries

- The raw export is evidence **as supplied by the provider/retrieval path**; preservation does not establish that every record inside it is true, complete, or authorized.
- Retrieval metadata and provider message IDs are provenance, not proof of the responsible human.
- A provider alert, session record, or device label does not by itself establish unauthorized access or attribution.
- Extraction, normalization, conversation reconstruction, Wordbook indexing, and analytical annotations are derived artifacts and must be stored separately from the raw object.
- The store never overwrites an existing content object to make a mismatch disappear. A hash mismatch is an integrity failure.

## Automation integration

The active ChatGPT export watcher should perform only:

1. detect a new `ChatGPT - Your data export is ready` message;
2. retrieve the export if the connected provider surface permits it;
3. invoke this preservation contract once with the available provider metadata;
4. retain the returned `receipt_id` and SHA-256 as the canonical downstream reference;
5. mark the provider export as processed only after preservation succeeds.

Feature-specific watchers must not retrieve a second copy. They consume a verified receipt later.
