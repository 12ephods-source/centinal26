# Wordbook — 100-Cycle Accumulated-Corpus Engine

Wordbook is a personal language intelligence system built around a living corpus of the user's language exposure. The 100-cycle engine is a core design feature, not a benchmark gimmick and not 100 independent copies of one agent loop.

## Canonical invariant

Each cycle consumes the exact accumulated corpus produced by the preceding accepted cycle:

`Corpus G0 -> C1 -> G1 -> C2 -> G2 -> ... -> C100 -> G100`

For cycle `n`:

- input generation MUST be `n-1`;
- output generation MUST be `n`;
- output `parent_sha256` MUST equal the active input corpus digest;
- skipped, duplicated, reset, or out-of-order cycles BLOCK;
- encounter and source history may not decrease;
- every cycle records evidence even when rejected;
- a rejected cycle places the lineage in `REVIEW_REQUIRED` rather than silently continuing;
- generation 100 is complete only after all preceding accepted generations exist in lineage.

This means cycle 73 is not another pass over the original import. It improves the corpus produced by cycle 72, which already incorporates accepted work from cycles 1-71.

## Ten stages / one hundred distinct objectives

### 1-10 — Corpus integrity

Provenance, exact duplicates, near duplicates, source identity, broken references, coverage, malformed text, reversible canonicalization, deletion/merge audit, reproducible integrity baseline.

### 11-20 — Lexical normalization

Token boundaries, case, lemmatization, part of speech, inflection families, spelling variants, abbreviations, named entities, morphology, confidence calibration.

### 21-30 — Sense modeling

Sense clustering, homographs, over-splitting, definitions by sense, personal sense frequency, technical senses, sense drift, unresolved polysemy, disambiguation learning, held-out calibration.

### 31-40 — Phrases and collocations

Multiword expressions, personal collocations, idioms, phrasal verbs, discourse markers, compounds, argument patterns, adjective-noun and verb-object patterns, jargon phrases, phrase calibration.

### 41-50 — Register and pragmatics

Register, interpersonal stance, marked usage, connotation, rhetorical function, genre differences, dialect variants, usage notes, pragmatic mismatch, calibration.

### 51-60 — Personal language model

Observed frequency, receptive versus productive vocabulary, personal collocations, lexical diversity, repeated weak words, independently reused words, confusion sets, explanation preferences, familiarity estimation, explicit-correction calibration.

### 61-70 — Graph and retrieval

Lexical graph, sense-constrained synonyms, contrast relations, morphology/etymology navigation, semantic neighborhoods, source-aware search, query expansion, related-word ranking, graph contradiction detection, frozen retrieval benchmark.

### 71-80 — Learning and mastery

Authentic recall prompts, cloze, sense contrast, morphology exercises, collocation exercises, forgetting risk, spaced review, priority ranking, exercise leakage detection, mastery calibration.

### 81-90 — Writing assistance

Context-appropriate learned vocabulary, misuse detection, register mismatch, underused mastered vocabulary, corpus-backed collocations, substitution explanations, repetition analysis, comparison with historical usage, meaning preservation, accepted/rejected suggestion calibration.

### 91-100 — Calibration and convergence

Evidence-path audit, confidence recalibration, ambiguity stress tests, malformed-input stress tests, regression tests, contradiction handling, reversible compaction, full corpus rebuild, generation-99 versus generation-0 comparison, final generation-100 lineage/evidence/unknowns report.

## Why this is not the same loop 100 times

The loop mechanics are reusable, but the *optimization target changes every generation*. Each `CycleSpec` has a unique objective and stage-specific required metrics. The engine validates that there are exactly 100 contiguous cycles and exactly 100 distinct objectives.

The changing target matters because Wordbook is building different layers of a language model over time. Early cycles establish trustworthy data. Middle cycles derive increasingly rich linguistic structure. Later cycles personalize retrieval, pedagogy, and writing assistance. Final cycles attack calibration, reproducibility, contradictions, and cumulative gain.

## State model

`CorpusSnapshot` records:

- generation number;
- corpus SHA-256;
- parent corpus SHA-256;
- immutable cumulative encounter count;
- immutable cumulative source count;
- current canonical entry count.

Canonical entries may merge or split as analysis improves, so the engine does not require `canonical_entry_count` to increase. Raw encounter and source history cannot decrease.

`CycleEvidence` binds:

- cycle and stage;
- objective;
- input digest;
- output digest;
- measured metrics;
- ACCEPT/BLOCK decision;
- reasons;
- its own deterministic SHA-256 evidence digest.

`EvolutionLedger` records the active generation, next required cycle, evidence chain, and terminal state.

## Open-source tool architecture

The 100-cycle engine is tool-agnostic. Each linguistic worker can be replaced as long as it emits the same bounded proposal/evidence contract. Suitable open-source components include:

- SQLite for the canonical local corpus and encounter/provenance ledger;
- SQLite FTS5 for local full-text search;
- spaCy or Stanza for optional tokenization/POS/lemma/syntactic enrichment;
- wordfreq for frequency priors;
- wordninja or equivalent only as a bounded candidate generator for segmentation, never canonical authority;
- WordNet/Open English WordNet for sense and lexical-relation candidates;
- Wiktionary-derived data for definitions, morphology, etymology, pronunciation, and usage candidates where licensing/provenance is preserved;
- sentence-transformers for optional local semantic retrieval where device resources permit;
- FSRS for spaced-review scheduling;
- an open-source coding/agent runtime such as Goose for bounded software-evolution proposals, subject to Automation OS security gates.

External lexical sources are evidence inputs, not silent replacements for the personal corpus. Their source, version, license, retrieval time, and confidence should be recorded.

## Controlled evolution boundary

Wordbook's corpus evolution and Wordbook's software evolution are separate layers.

Corpus evolution performs the 100 linguistic improvement cycles against accumulated corpus state.

Software evolution may improve the Wordbook implementation using the Automation OS controlled-evolution framework. Software agents may propose patches, but they do not get authority to rewrite corpus history, evaluators, security policy, or production state.

The two loops can interact only through explicit versioned interfaces:

`software version + corpus generation + cycle spec + evaluator version -> evidence`

That prevents a model from improving its score by changing the data, changing the test, or quietly redefining what a successful cycle means.

## Core product consequence

The user experience should expose this as one evolving Wordbook, not as 100 technical jobs. Internally, every dictionary entry, example, sense, collocation, learning prompt, and writing recommendation can carry the corpus generation and evidence lineage that produced it.

The result is a private, cumulative language model whose later intelligence is earned from prior corpus work rather than regenerated from scratch.
