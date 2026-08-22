# Frost Sentinel Independent Evidence Verification v1

## Purpose

This layer independently verifies the artifacts produced by `tools/dfir/FROST_ANDROID_EVIDENCE_GUARDIAN_v3.1.sh` without importing or executing collector implementation logic.

It is read-only. It does not collect evidence, modify retained runs, repair a damaged chain, infer an attacker, or promote a claim to device-origin merely because the collector recorded Android metadata.

## Independently checked software properties

For every custody-ledger record, the verifier recomputes and checks:

- SHA-256 hash-chain continuity for `custody_chain.tsv`;
- manifest SHA-256 identity;
- every file listed in the run manifest;
- archive SHA-256 and its sidecar;
- archived bytes against the sealed manifest rather than trusting only the live run directory;
- run/case/operator metadata consistency;
- runtime-class → claim-scope mapping;
- acquisition start/finish chronology and custody-record chronology;
- duplicate run identifiers;
- minimum required run count.

A successful verification produces a normalized acquisition/custody timeline.

## Claim boundary

`PASS_ARTIFACT_INTEGRITY_PROVENANCE_AND_ACQUISITION_TIMELINE` means that the retained evidence bundle is internally consistent under the independent verifier and that its acquisition/custody chronology can be reconstructed.

It does **not** establish:

- that a self-recorded `ANDROID_TERMUX` runtime label came from a particular handset;
- that an observed artifact was malicious;
- attacker identity or forensic attribution;
- semantic truth of captured application/provider data;
- empirical/scientific truth.

Live handset-origin claims still require evidence whose origin is independently grounded at the Android/Termux boundary. Stronger forensic conclusions may additionally require external/provider corroboration.

## Qualification model

CI qualification uses the actual shell collector in an isolated host directory to create sealed synthetic acquisitions. A structurally separate Python verifier then evaluates those artifacts. Negative tests alter the run bytes, archive, and custody chain and require fail-closed rejection. Android-fixture mode is also tested to prove that simulation cannot become device-origin evidence by configuration alone.

This establishes a software-level independent verification path and acquisition-timeline substrate for Frost Sentinel. It does not claim production deployment or live-device corroboration.
