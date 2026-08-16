# Wordbook v0.1 — Personal Language Index

Status: **EXPERIMENTAL**. Host CI is validated; Android/Termux physical validation remains a separate empirical gate until the device script is actually executed on a phone.

Wordbook is a local-first language evidence module for Centinal26. It imports authored text, preserves source identity, computes exact word and 2–8-word phrase occurrences, separates attribution classes, records explicit rejection evidence, and runs a fixed 100-generation bounded evolution campaign over derived policy parameters.

## Non-negotiable boundary

Original source text and occurrence evidence are immutable inputs to analysis. Evolution may change derived policy parameters; it does not rewrite the corpus, fabricate observations, self-modify executable code, or bypass Centinal26 authorization/promotion controls.

## Core commands

```bash
centinal26-wordbook --db wordbook.sqlite3 ingest-chatgpt conversations.json
centinal26-wordbook --db wordbook.sqlite3 query basically
centinal26-wordbook --db wordbook.sqlite3 top-words --limit 100
centinal26-wordbook --db wordbook.sqlite3 top-phrases --limit 100
centinal26-wordbook --db wordbook.sqlite3 reject basically --reason "not my voice"
centinal26-wordbook --db wordbook.sqlite3 evolve --output wordbook_evolution.json
```

## Android / Termux gate

From a Centinal26 checkout on the Wordbook branch or a later release containing Wordbook:

```bash
bash scripts/install-wordbook-termux.sh
```

The script does not run `pkg update`; it uses the Python already available in the Centinal26/Termux environment, installs the current checkout with pip, executes an isolated synthetic corpus test, exercises attribution and the full 100-generation campaign, and writes:

```text
~/.local/state/centinal26/wordbook/WORD_BOOK_DEVICE_VALIDATION_REPORT.json
~/.local/state/centinal26/wordbook/WORD_BOOK_DEVICE_VALIDATION_REPORT.json.sha256
```

The synthetic validation database is temporary and is deleted after the gate, so validation text cannot contaminate the personal corpus.

To validate first and then import a real ChatGPT export into the persistent Wordbook database:

```bash
bash scripts/install-wordbook-termux.sh /path/to/conversations.json
```

A `TERMUX_SELFTEST_PASS` report is physical execution evidence only. It does not authorize promotion by itself.

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
- Quote/meta classification is deliberately conservative and should evolve only behind regression tests.
- FTS5 is opportunistic. Exact counts continue to work on SQLite builds without FTS5.
- Spoken transcripts, email, generic document, and file-organizer adapters are not yet connected.
- The first 100-loop engine evolves bounded analysis policy parameters; it does not self-edit source code.
- No claim of exhaustive account-wide counts is valid until a complete corpus has been imported and deduplicated.
- The Termux gate is prepared but is not considered executed until its report comes from an actual Android/Termux environment.

## Acceptance target

Given a complete ChatGPT export, Wordbook must reproducibly enumerate every directly authored word and indexed phrase, retain the source of every observation, distinguish attribution classes, and answer exact-count queries without using an LLM for counting.
