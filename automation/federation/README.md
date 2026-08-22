# Frost Unified Cross-Project Federation

This subsystem is the canonical portfolio map for the user's projects.

The projects are **combined as a federation**, not flattened into one trust domain. `12ephods-source/centinal26` is the canonical orchestration and engineering state authority. Every account goal in `automation/account_goals/GOALS.json` has exactly one canonical owning project family, while projects may depend on shared components and exchange typed evidence/state edges.

## Canonical shared components

- **C01 Frost Core** — intent, canonical state, orchestration, lifecycle, project graph.
- **C02 Guardian** — defensive observation, cybersecurity evidence, bounded recovery.
- **C03 Provenance & Recovery Engine** — immutable provenance, reconstruction, canonical storage, recovery evidence.
- **C04 Epistemic Guard** — verification, contradiction handling, completion semantics, adversarial criticism.
- **C05 Frost Agent Fabric** — typed capability gateway, bounded execution, device/provider adapters.

## Canonical project families

The registry currently unifies these project families under the shared control plane:

- Automation OS / Centinal26
- Frost Agent Fabric
- Frost Sentinel / Guardian
- Provenance & Recovery Engine
- Dedupe/Organizer
- AAARD / Second Brain
- Conversation Compass / Account Intelligence
- Epistemic Guard
- Physics Research
- Test-a-Theory
- OpenQuestRPG
- Creative Canon Engine
- Productizer / Economic Value Engine

Historical names, predecessor programs, and compatibility surfaces are mapped to canonical owners in `projects.json`; they do not create parallel sources of truth.

## Combination invariants

Unification never implies authority inheritance. Physics retains scientific/empirical gates; Cybersecurity retains evidence/defense boundaries; Android/Termux remains the only source of authentic physical-device execution evidence; projections remain rebuildable and non-authoritative; signatures/hashes attest integrity rather than truth; and detection remains separate from mutation.

The registry is fail-closed. `project_federation.py` rejects duplicate or unknown projects/components, dependency cycles, ambiguous aliases, missing trust/state authority, missing mandatory invariants, and any account goal that has zero or multiple canonical project owners.

Run:

```bash
python automation/federation/project_federation.py
python -m pytest -q tests/test_project_federation.py
```

A passing federation result establishes structural portfolio consistency only. It does not promote scientific truth, forensic attribution, physical-device validation, deployment, or production readiness.
