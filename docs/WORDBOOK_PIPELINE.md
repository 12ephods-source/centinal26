# Wordbook v0.2 — Canonical Export Evidence Pipeline

Status: **EXPERIMENTAL / HOST-QUALIFICATION REQUIRED**.

Wordbook v0.2 composes the Wordbook language engine with Centinal26's neutral provider-export evidence store. The raw ChatGPT export is acquired and preserved once; Wordbook consumes only a re-verified immutable object or receipt. Wordbook does not own provider acquisition and does not create a parallel raw-export archive.

## Canonical flow

```text
provider export ZIP
    -> centinal26.export_evidence preserve
    -> immutable SHA-256 object + provenance receipt
    -> verify_receipt
    -> Wordbook archive safety checks
    -> authored-message indexing
    -> deterministic exhaustive word/phrase dictionary
    -> fixed 100-generation bounded analysis campaign
    -> hashed derived artifacts
```

Raw evidence and derived artifacts remain distinct. A Wordbook result does not rewrite the raw provider export or its receipt.

## CLI

Process a newly downloaded ChatGPT export:

```bash
centinal26-wordbook-pipeline source ~/storage/downloads/chatgpt-export.zip
```

Process an export already preserved by the canonical export watcher/control plane:

```bash
centinal26-wordbook-pipeline receipt <receipt-id>
```

Discover the newest local ChatGPT export ZIP in standard Termux download directories:

```bash
centinal26-wordbook-pipeline latest
```

The pipeline writes private local artifacts under:

```text
~/.local/state/centinal26/wordbook/wordbook.sqlite3
~/.local/state/centinal26/wordbook/WORD_BOOK_DICTIONARY.json
~/.local/state/centinal26/wordbook/WORD_BOOK_EVOLUTION.json
~/.local/state/centinal26/wordbook/LAST_CORPUS_BUILD.json
```

The report binds the provider receipt ID, raw SHA-256, raw byte size, verified content-addressed object path, archive-member hashes, corpus digest, dictionary file SHA-256, evolution file SHA-256, and database path.

## Termux consumer

```bash
bash scripts/process-wordbook-export-termux.sh
```

With no argument, the script checks the standard Termux Downloads locations. If no ChatGPT export exists, it exits cleanly. If the latest local export is already represented by the current corpus-build report and dictionary, it exits without rerunning the 100-loop campaign.

Explicit file:

```bash
bash scripts/process-wordbook-export-termux.sh /path/to/export.zip
```

Canonical receipt:

```bash
bash scripts/process-wordbook-export-termux.sh --receipt <receipt-id>
```

This one-shot interface is suitable for the existing Centinal26 worker/scheduler. It deliberately does not implement a second provider watcher; the canonical export watcher owns acquisition.

## Dictionary semantics

`WORD_BOOK_DICTIONARY.json` is deterministic for a fixed Wordbook database state and contains:

- every directly authored normalized word and exact occurrence count;
- every indexed directly authored 2–8 word phrase and exact occurrence count;
- meta-reference word counts kept separate from ordinary usage;
- explicit rejection records.

Quoted text and assistant-generated text remain excluded from ordinary authored vocabulary according to the Wordbook attribution rules.

## Evidence and idempotency

- Raw ZIP bytes are preserved by `centinal26.export_evidence` before parsing.
- The canonical receipt/object is rehashed before Wordbook consumes it.
- Reprocessing the same provider source returns `DUPLICATE_SOURCE` at the evidence layer.
- Wordbook source/message identities and archive-import records prevent duplicated corpus observations.
- An unchanged local export can be skipped by the Termux one-shot consumer.
- Tampered canonical raw objects fail before derived analysis.

## Remaining empirical gates

Host CI success does not imply Android validation. The physical gate remains execution of the Termux route on an actual Android/Termux device using a real ChatGPT export or canonical receipt. No exhaustive account-wide vocabulary claim is valid until the complete intended corpus is acquired, imported, deduplicated, and its completeness limitations are recorded.

The current ChatGPT `conversations.json` parser materializes the top-level JSON structure in memory. Very large exports may require a streaming parser before low-memory Android operation can be claimed robust.
