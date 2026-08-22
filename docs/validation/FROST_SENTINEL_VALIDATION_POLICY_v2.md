# Frost Sentinel Validation Policy v2

## Canonical correction

Frost Sentinel does **not** impose a project-wide requirement for genuine Android/Termux
execution. Validation is scoped to the claim being made.

| Validation class | What it can establish |
|---|---|
| `HOST_OR_SESSION` | Software correctness, deterministic transforms, hashing/sealing, manifests, chain verification, replay, parsing, state transitions, failure handling, packaging, and other environment-independent behavior. |
| `ANDROID_FIXTURE` | All host/session claims plus Android-specific behavior exercised against controlled Android fixtures, mocked command output, or an emulator/test harness. |
| `ANDROID_TERMUX` | All applicable software claims plus claims about evidence actually collected from that live Android/Termux environment. |
| `EXTERNAL_CORROBORATED` | Independent verification of hashes, provenance, provider records, or other evidence by a separate trusted source/process. |

## Governing rule

`required_validation = minimum environment necessary to support the specific claim`

Therefore:

- A host-tested collector may be **SOFTWARE_VERIFIED** without any handset run.
- An Android-fixture-tested collector may be **ANDROID_LOGIC_VERIFIED** without a physical handset.
- A handset run is necessary only for **DEVICE_ORIGIN_VERIFIED** or other live-device-state claims.
- Lack of a handset run must never downgrade unrelated host-verifiable work to `PENDING`.
- Simulation may not be relabeled as device-origin evidence.
- Device-origin evidence may still require independent corroboration for stronger forensic conclusions.

## Status vocabulary

Preferred statuses:

- `SOFTWARE_VERIFIED`
- `ANDROID_LOGIC_VERIFIED`
- `DEVICE_ORIGIN_VERIFIED`
- `EXTERNAL_CORROBORATED`
- `NOT_TESTED`
- `FAILED`
- `INAPPLICABLE`

Avoid the ambiguous project-wide state `PENDING_PHYSICAL` except when the specific claim
being tracked is itself a physical/device-origin claim.
