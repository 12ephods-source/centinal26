# Release Notes — v1.0.0-rc3-ga-campaign

RC3 is a host-validated release candidate. It does not claim physical Android validation.

## Added

- Resumable GA campaign orchestration.
- Explicit host refusal for physical campaign execution.
- Optional host smoke mode that cannot satisfy physical certification.
- Public-key-only peer pairing archives.
- Explicit fingerprint confirmation before peer trust is written.
- Campaign state persistence and restart support.
- Automatic attestation import after Android, endurance, and device-sync gates.
- Final certification execution and persisted campaign decision.

## Unchanged authority boundaries

- Model outputs remain unverified proposals.
- Remote peer events remain proposal-only until governed merge.
- Device signatures prove key possession and integrity, not factual truth.
- Physical Android, endurance, and two-device sync evidence are still mandatory for GA PASS.
- Release promotion still requires a PASS certificate and explicit actor-attributed promotion.
