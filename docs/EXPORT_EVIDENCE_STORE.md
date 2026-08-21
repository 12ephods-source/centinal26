# Neutral provider export evidence store

Status: `HOST_CANDIDATE / EVIDENCE_PRESERVATION`

A provider data export is acquired once, preserved as raw bytes, bound to SHA-256 and provider provenance, and then reused by downstream consumers. Preservation never establishes that records inside the export are true, complete, authorized, or attributable to a particular person.

Default root:

`~/.local/share/centinal26/evidence/exports/`

Layout:

- `objects/sha256/<prefix>/<sha256>` — raw content-addressed bytes;
- `receipts/<receipt_id>.json` — immutable provenance receipt;
- `index/receipts.jsonl` — append-only receipt index;
- `.ingest.lock` — local serialization lock.

The preservation layer does not extract archives. Extraction, normalization, conversation reconstruction, indexing, and analytical annotations are derived artifacts and must remain separate from raw evidence.

Strong provider identities such as a message ID or export ID may not later bind to different bytes. Identical bytes may be reused across distinct legitimate source receipts. A stored object is re-hashed before downstream use.

Example:

```bash
python -m centinal26.export_evidence preserve /path/to/export.zip \
  --provider provider-name \
  --message-id provider-message-id
python -m centinal26.export_evidence verify RECEIPT_SHA256
```

Successful preservation states are `PRESERVED`, `REUSED_OBJECT`, and `DUPLICATE_SOURCE`. Identity conflicts and object-integrity failures fail closed.

Automation should retrieve an export only through an independently authorized connector or local process, preserve it once, retain the receipt identifier and SHA-256, and make downstream capabilities consume that verified receipt rather than retrieving duplicate copies.
