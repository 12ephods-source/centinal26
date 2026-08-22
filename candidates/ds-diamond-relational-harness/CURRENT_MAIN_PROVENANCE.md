# Current-main transplant provenance

Status: `EXPERIMENTAL / CURRENT-MAIN REQUALIFICATION REQUIRED`

This directory is a byte-for-byte transplant of the previously qualified dS2 relational candidate from old head `c8179937afe6fcee9c29fd64537a13b2be105a51`, except that its retired KMS dependency is now satisfied by a narrow compatibility adapter.

The adapter delegates to the current canonical Phase-I implementation at `candidates/phase1-regulated-kms-bkm-v2/harness.py`; it does not reimplement the KMS, modular, cocycle, relative-entropy, or BKM machinery.

Canonical parent evidence at transplant:

- Phase-I BKM/cocycle baseline plus independent BKM oracle: main commit `80204576dc8506bfb6254e12ac471536886111bf`.
- Clock-regulator convergence: commit `58ca997a234ed0010fef30496ec4bbd4b7e99949`.
- Frozen predecessor dS2 candidate: head `c8179937afe6fcee9c29fd64537a13b2be105a51`.

Promotion rule: old CI evidence is provenance only. This transplant must pass its own current-main Python 3.11-3.13 CI before its finite dS2 relational baseline can be treated as current canonical evidence.

Scope remains finite Type-I/regulator evidence only. No continuum factor-type, gravitational canonical-energy, Einstein-dynamics, or global-gluing claim is promoted.

© Robert Frost
