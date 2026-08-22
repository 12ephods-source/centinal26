# Frost Sentinel Canonical Project State

Date: 2026-08-22
Primary project: **Sentinel / Cybersecurity / P04 Frost Sentinel**

## Canonical validation rule

Frost Sentinel uses **claim-scoped validation**, not a project-wide physical-device blocker.

`required_validation = minimum environment necessary to support the specific claim`

Accordingly:

- Environment-independent software correctness, deterministic transforms, hashing/sealing, manifests, parsing, replay, packaging, and failure handling may be `SOFTWARE_VERIFIED` from host/session validation.
- Android-specific logic may be `ANDROID_LOGIC_VERIFIED` from fixtures/emulation where the claim does not require live handset provenance.
- Only claims about evidence actually originating from the current live handset require `DEVICE_ORIGIN_VERIFIED` / `ANDROID_TERMUX`.
- Independent provider/hash/provenance confirmation is `EXTERNAL_CORROBORATED`.
- Older records using `PENDING_PHYSICAL` as a project-wide state are historical and superseded for current governance.

## Investigation state

The investigation is beyond the question of whether there is material worth investigating. Current records support a mature DFIR architecture, provider-origin account/security events, contemporaneous incident testimony, recovered provider transaction anchors, and partial device lineage. They do not yet establish event-specific authorization or human actor attribution.

Canonical evidentiary ladder:

`provider/preserved event -> provider transaction/notification anchor -> session/client context -> stable device candidate -> common action/session/device key -> controller/possession -> authorization -> human attribution`

Principal open evidentiary gate:

`provider transaction/notification anchor -> common provider session/device key`

## Highest-value current findings

1. Exact provider anchors (`eid`, `aneid`, notification IDs, Takeout job IDs, and hashed recovery-flow identifiers) exist for multiple January account-control events and are stronger correlation targets than timestamps alone.
2. Three distinct January Takeout cycles are established in provider records; the middle Cycle B index was materialized and hashed, while Cycle A/C archive bytes remain unrecovered in current connected searches.
3. Distinct Samsung A15 and A06 lineages are supported. The A15 branch contains high-value close temporal correlations; the A06 branch includes a provider-reported model-specific action. Neither is sufficient by itself for human attribution.
4. Exact recovery is cryptographic/provenance-defined, not filename-defined. A post-suspected-compromise baseline is not proof of cleanliness.
5. AI/model output can accelerate extraction and correlation but cannot independently promote a claim to primary observed evidence.

## Validation state

- Forensic acquisition / sealing / manifest / deterministic transformation logic: `SOFTWARE_VERIFIED` where prior host validation is recorded.
- Android-specific logic exercised only outside the live handset: at most `ANDROID_LOGIC_VERIFIED` when supported by fixture evidence.
- Current handset evidence-origin claims: `NOT_TESTED` unless an authentic device-origin artifact is present and verified.
- Provider-authenticated records and independently checked primary artifacts: `EXTERNAL_CORROBORATED` where the source record explicitly supports that status.

The absence of a handset run does **not** block unrelated software or provider-evidence work. It only leaves live-handset-origin claims open.

## Explicitly unresolved

- Common provider session/device key for the highest-value disputed events.
- Owner authorization, event by event.
- Controller/possession at relevant event times.
- Resolution of remaining Android configuration identifiers.
- Recovery/diffing of Takeout Cycle A/C against Cycle B.
- Current-handset comparison against genuinely trusted provenance.
- Human actor attribution.

## Epistemic invariants

- `possible evidence exists != evidence currently available != verified evidence != final conclusion`
- `provider event != session identity != device identity != authorization != human actor`
- `hash/fixity != historical authenticity`
- `model inference != observed primary evidence`
- `not found in current query != never existed`
- `simulation != device-origin evidence`

## Highest-value next actions

1. Correlate exact provider anchors to session creation/refresh, IP/user-agent, provider device/session IDs, token issuance/revocation, recovery-flow state, and common internal audit keys.
2. Recover Cycle A and C Takeout bytes if available; hash and diff A/B/C across Android Device Configuration, Access Logs, Chrome Device Information, and Google Account records.
3. Resolve remaining Android configuration IDs by model/stable identifier.
4. Run live-handset collection only for claims that specifically require current-device provenance; verify hashes/manifests independently.
5. Compare current handset state against trusted Git/package/vendor/backup references rather than a post-incident baseline alone.
6. Adjudicate authorization per disputed event before attempting human attribution.

## Monolith workstream disposition

The forensic-agent/monolith development belongs in Sentinel as defensive runtime tooling. The durable design invariant is to keep one deployable artifact while enforcing strict internal boundaries:

`acquisition -> persistence -> analysis -> alerting -> verification`

A monolith may remain one file without becoming unstructured. Implementations should be materialized as files and executed under their intended runtime rather than pasted line-by-line into an incompatible shell.
