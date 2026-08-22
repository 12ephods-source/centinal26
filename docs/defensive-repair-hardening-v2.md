# Defensive Repair Hardening v2

This increment hardens the AIxCC-derived defensive repair foundation without expanding execution authority.

## Implemented gates

1. Altered original source is rejected rather than silently reinterpreted.
2. Altered repaired source cannot be independently verified.
3. Regression-inducing repairs fail verification.
4. Tampered patches fail patch-identity verification.
5. Candidate repair rejects unpinned inputs.
6. Identical benchmark inputs produce deterministic canonical evidence.
7. Evidence binds source, repair, and patch with distinct SHA-256 identities.
8. Every adapter operation fails closed for unauthorized fixture IDs and authorization scopes.
9. Capability metadata explicitly denies arbitrary source input, network targeting, and shell authority.

## Remaining qualification

The exact branch head must pass the repository's applicable CI, validate, automation, governance, federation, release, and Mature Product Qualification gates before merge. CI success does not establish Android/device validation or scientific validity.
