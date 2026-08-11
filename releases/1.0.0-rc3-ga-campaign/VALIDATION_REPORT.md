# Automation Canonical Platform v1.0.0-rc3 Validation Report

Release class: **release candidate / GA campaign orchestration**  
Schema: **9**  
Host validation: **PASS**  
Physical Android/Termux validation: **OPEN**  
Expected certification before physical evidence: **REVIEW**

## Host-validated additions

- Resumable GA campaign orchestration.
- Default refusal to run physical gates on a non-Android/Termux host.
- Host smoke mode cannot satisfy physical certification.
- Public-key-only peer pairing package.
- Explicit expected-fingerprint confirmation before peer trust is persisted.
- Campaign state survives interruption and can be resumed.
- Android, endurance and device-sync attestations are imported through the existing signed-evidence boundary.
- Final campaign step invokes recovery and release certification without bypassing PASS/REVIEW/FAIL policy.

## Regression coverage

The isolated host matrix covers runtime self-test, persistent queue recovery, workflows, model routing, local-model context, resource governance, release certification, legacy and Ed25519 federation, device attestations, migration, Android host harness behavior, GA campaign pairing, and CLI workflow execution.

## Upgrade/rollback evidence

Actual RC2 → RC3 upgrade testing preserved:

- canonical knowledge: 5 → 5
- state snapshots: 1 → 1
- Ed25519 keypairs: 1 → 1

Actual RC3 → RC2 rollback restored the RC2 application while preserving the same state and removed the RC3-only `automation-platform-ga` wrapper.

## Remaining empirical gates

RC3 is not GA. The following still require execution on real devices:

1. Signed physical Android/Termux validation.
2. Signed endurance validation under the intended duration and load.
3. Signed two-device synchronization validation using a locally pinned peer public key.
4. Final certification yielding PASS.
5. Explicit human-attributed release promotion.
