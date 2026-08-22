# Current-main transplant provenance

Status: `QUALIFIED_ON_CURRENT_MAIN`

This directory is a byte-for-byte transplant of the previously qualified dS2 relational candidate from old head `c8179937afe6fcee9c29fd64537a13b2be105a51`, except that its retired KMS dependency is satisfied by a narrow compatibility adapter.

The adapter delegates to the canonical Phase-I implementation at `candidates/phase1-regulated-kms-bkm-v2/harness.py`; it does not reimplement the KMS, modular, cocycle, relative-entropy, or BKM machinery.

Canonical evidence:

- Phase-I BKM/cocycle baseline plus independent BKM oracle: `80204576dc8506bfb6254e12ac471536886111bf`.
- Clock-regulator convergence: `58ca997a234ed0010fef30496ec4bbd4b7e99949`.
- Frozen predecessor dS2 candidate: `c8179937afe6fcee9c29fd64537a13b2be105a51`.
- Current-main requalification: PR #422, merged as `02e23a4c25c43f24220869876c778683a6cbe326`.

Qualification result: dedicated dS2 harness PASS on Python 3.11, 3.12, and 3.13; all repository qualification workflows PASS. The current-main artifact reports 9/9 strict gates PASS.

Scope remains finite Type-I/regulator evidence only. No continuum factor-type, gravitational canonical-energy, Einstein-dynamics, or global-gluing claim is promoted.

© Robert Frost
