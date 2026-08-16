# Wordbook v0.1 — Personal Language Index

Status: **EXPERIMENTAL**. Host validation does not imply Android/Termux validation.

Wordbook is a local-first language evidence module for Centinal26. It imports authored text, preserves source identity, computes exact word and 2–8-word phrase occurrences, separates attribution classes, records explicit rejection evidence, and runs a fixed 100-generation bounded evolution campaign over derived policy parameters.

## Non-negotiable boundary

Original source text and occurrence evidence are immutable inputs to analysis. Evolution may change derived policy parameters; it does not rewrite the corpus, fabricate observations, self-modify executable code, or bypass Centinal26 authorization/promotion controls.

## Core commands

```bash
centinal26-wordbook --db wordbook.sqlite3 ingest-chatgpt conversations.json
centinal26-wordbook-archive --db wordbook.sqlite3 chatgpt-export.zip
centinal26-wordbook --db wordbook.sqlite3 query basically
centinal26-wordbook --db wordbook.sqlite3 top-words --limit 100
centinal26-wordbook --db wordbook.sqlite3 top-phrases --limit 100
centinal26-wordbook --db wordbook.sqlite3 reject basically --reason "not my voice"
centinal26-wordbook --db wordbook.sqlite3 evolve --output wordbook_evolution.json
```

## Direct ChatGPT ZIP ingestion

`centinal26-wordbook-archive` accepts the ZIP delivered by ChatGPT data export. It does not extract the archive into the filesystem. Instead it locates exactly one safe `conversations.json` member, streams that member to an isolated temporary file, hashes both the ZIP and the JSON member, invokes the existing Wordbook parser, records an archive-import ledger entry, and deletes the temporary file.

The archive adapter rejects ambiguous duplicate `conversations.json` members, traversal-style member names, symbolic links, encrypted members, invalid ZIPs, configured size-limit violations, excessive member counts, and excessive compression ratios. Limits are configurable from the CLI.

Example with an import report:

```bash
centinal26-wordbook-archive \
  --db ~/.local/state/centinal26/wordbook/wordbook.sqlite3 \
  --report ~/.local/state/centinal26/wordbook/LAST_CHATGPT_IMPORT.json \
  ~/storage/downloads/chatgpt-export.zip
```

## Android / Termux gate

From a Centinal26 checkout containing Wordbook:

```bash
bash scripts/install-wordbook-termux.sh
```

The script uses the Python already available in the Centinal26/Termux environment, installs the current checkout, builds an isolated synthetic ChatGPT ZIP, runs that ZIP through the real archive adapter and Wordbook engine, verifies attribution and exact counts, exercises the full 100-generation campaign, and writes:

```text
~/.local/state/centinal26/wordbook/WORD_BOOK_DEVICE_VALIDATION_REPORT.json
~/.local/state/centinal26/wordbook/WORD_BOOK_DEVICE_VALIDATION_REPORT.json.sha256
```

The synthetic ZIP and validation database are temporary and are deleted after the gate, so validation text cannot contaminate the personal corpus.

To validate the device and then import a real ChatGPT export in the same run:

```bash
bash scripts/install-wordbook-termux.sh ~/storage/downloads/chatgpt-export.zip
```

The script also accepts an already extracted `conversations.json`. A `TERMUX_SELFTEST_PASS` report is physical execution evidence only. It does not authorize promotion by itself.

## Attribution classes

Wordbook stores direct authored usage separately from quoted text, meta-reference, AI-generated text, AI-accepted text, AI-rejected text, and other text. This prevents discussion of a word from being silently treated as evidence that the word is characteristic of the user's ordinary vocabulary.

## 100-generation campaign

The campaign is split into ten ten-generation phases:

1. corpus integrity
2. token model
3. phrase discovery
4. context classification
5. personal vocabulary
6. writing structure
7. temporal evolution
8. distinctiveness
9. voice reconstruction
10. adversarial verification

Every generation records its phase, baseline score, candidate score, promotion decision, policy hashes, and the corpus evidence hash. A candidate is promoted only when its deterministic benchmark score strictly improves. Rejected candidates remain represented in the evolution report.

## Current limitations

- ChatGPT import supports the standard `conversations.json` mapping structure but has not yet been validated against every historical export variant.
- The JSON parser currently materializes the top-level export JSON in memory; very large histories may require a future streaming parser.
- Quote/meta classification is deliberately conservative and should evolve only behind regression tests.
- FTS5 is opportunistic. Exact counts continue to work on SQLite builds without FTS5.
- Spoken transcripts, email, generic document, and file-organizer adapters are not yet connected.
- The first 100-loop engine evolves bounded analysis policy parameters; it does not self-edit source code.
- No claim of exhaustive account-wide counts is valid until a complete corpus has been imported and deduplicated.
- The Termux gate is prepared but is not considered executed until its report comes from an actual Android/Termux environment.

## Acceptance target

Given a complete ChatGPT export, Wordbook must reproducibly enumerate every directly authored word and indexed phrase, retain the source of every observation, distinguish attribution classes, and answer exact-count queries without using an LLM for counting.
