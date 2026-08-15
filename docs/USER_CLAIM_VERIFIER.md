# User Claim Verifier

The User Claim Verifier is a provenance-first subsystem for converting user statements into atomic claims and evaluating each claim against explicit evidence.

## Core invariant

**Documentation is not verification. Repetition is not corroboration. Successful software execution is not scientific validation.**

The verifier preserves supporting and adverse evidence simultaneously and produces deterministic, hash-addressed claim records.

## Verdicts

- `VERIFIED` — high-quality independent primary evidence supports the claim and no equal-or-stronger contradiction is present.
- `PARTIALLY_VERIFIED` — a computational or mathematical result is reproducible, but independent empirical validation is absent or incomplete.
- `DOCUMENTED_ONLY` — the available record establishes that the claim was written, proposed, reported, or published, but not that the underlying proposition is true.
- `PREDICTION` — forward-looking technological, economic, or empirical claim that requires future or external testing.
- `CONTRADICTED` — equal-or-higher quality adverse evidence outweighs supporting evidence.
- `INSUFFICIENT_EVIDENCE` — the minimum evidence needed for a defensible verdict has not been supplied.

## Evidence tiers

1. Conversation assertion.
2. Authored document or manuscript.
3. Contemporaneous record, provenance record, log, or repository artifact.
4. Reproducible execution with pinned inputs and outputs.
5. Independent primary external evidence.

Independence and reproducibility add weight but do not change the meaning of the source.

## Inputs

- `provenance/user_claims/2026-08-14_claims.json` — atomic claim registry.
- `provenance/user_claims/2026-08-14_evidence.json` — curated evidence records.
- repository tree — searched automatically for documentary matches.

## One-command run

```bash
python scripts/run_user_claim_verification.py
```

Generated files:

- `build/user_claim_verification/claim_verification_report.json`
- `build/user_claim_verification/claim_verification_report.md`
- `build/user_claim_verification/claim_ledger.jsonl`
- `build/user_claim_verification/claim_matrix.csv`
- `build/user_claim_verification/unresolved_evidence_requests.md`
- `build/user_claim_verification/evidence_manifest.json`

Every result record has a canonical SHA-256. The manifest hashes all generated outputs.

## Automation

`.github/workflows/user-claim-verification.yml` runs on:

- relevant pull requests;
- relevant pushes to `main`;
- manual dispatch;
- a daily scheduled audit.

The workflow runs unit tests, regenerates all claim documents, validates the ledger, and uploads the whole verification package as a GitHub Actions artifact.

## Adding evidence

Evidence should be atomic and source-specific. A self-authored manuscript can establish what the manuscript says, but it must not be marked independent. An independent experiment or official dataset may be independent, but it must still be tied to the exact claim and methodology.

For computational claims, preserve at minimum:

- source commit SHA;
- environment/dependency lock;
- input dataset hashes;
- random seeds if applicable;
- run/job identity;
- output hashes;
- independent rerun identity when available.

For public metrics or infrastructure-use claims, prefer platform exports or provider records over screenshots or retrospective statements.

## Scope

This subsystem verifies claims against evidence available to the repository and evidence deliberately imported into its ledger. It does not infer truth from popularity, AI agreement, manuscript language, or search-engine visibility. External web/search adapters can feed curated evidence records, but automatic network retrieval must preserve URL, retrieval timestamp, content hash, excerpt, and source-independence metadata before it affects a verdict.

© Robert Frost. All Rights Reserved.
