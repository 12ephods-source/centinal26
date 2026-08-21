# Automation OS Universal Installer v3.0

This adds a manifest-driven Android/Termux installer framework.

Security invariants:
- canonical remote modules are pinned to immutable Git commits and expected Git blob identities;
- framework files are SHA-256 pinned by the versioned Termux bootstrap;
- unregistered components fail closed;
- no credentials or signing private keys are embedded;
- Android permissions and user authentication are not bypassed.

Initial registered profile:
- `android-fleet` -> `FROST_FLEET_BOOTSTRAP_v1.7.sh`

This PR intentionally does not claim that Guardian, Sentinel, AICCEP, SDOS, Physics, or Cybersecurity workload packages have canonical install sources until those sources are separately registered and validated.
