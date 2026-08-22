# Frost Sentinel Priority Execution Plan

Date: 2026-08-22

1. **Reacquire January 12 part 10:** `takeout-20260112T092608Z-10-001.zip` was historically materialized and analyzed successfully. Reacquire any surviving copy and compare SHA-256 against the recorded `0f8a81ee502417b05bb25bead83dabda74361ed318ae6588edfe742059bd83a5`. Do not confuse historical acquisition with current byte possession.
2. **Recover Cycle B Google Account originals:** prioritize the indexed `ChangeHistory` and `SubscriberInfo` files or equivalent provider records. Hash on acquisition and search for exact transaction/session/device joins. Historical ChangeHistory-derived parsing exists, but the original HTML bytes are not currently materialized.
3. **Recover remaining January 12 Takeout parts:** Cycle B's Drive index records parts 001, 6, 8, 10, and 12. Two part-6 Drive folders are visible as derivative copies. Recover exact bytes where possible, inventory cryptographically, and compare against later snapshots.
4. **Provider-anchor join:** use exact event/notification anchors to correlate session creation/refresh, IP, user-agent, provider device/session IDs, token state, and internal audit keys.
5. **Cross-snapshot recovery:** recover Takeout A/C, then cryptographically inventory and diff A/B/C, prioritizing Google Account, Access Log Activity, Android Device Configuration, and Chrome Device Information.
6. **Device resolution:** map unresolved Android configuration identifiers using stable provider/hardware joins; never infer physical-device count from record count or model strings alone.
7. **Access Log recovery:** preserve the recovered hashed Devices CSV and continue bounded attempts to materialize the larger Activities CSV. Retain the historical 47,666-row part-10 validation as derived historical evidence, not a substitute for current source bytes.
8. **Claim-scoped handset validation:** keep the single read-only Android health gate; execute device collection only where a claim requires live-device provenance and never duplicate the gate while it is live.
9. **Trusted-provenance comparison:** compare handset files/configuration against known-good upstream sources, not only a current baseline.
10. **Authorization adjudication:** classify each disputed event as authorized / disputed / unknown from contemporaneous evidence.
11. **Attribution gate:** only after session/device/control/authorization joins are satisfied, evaluate human attribution with independent corroboration.

## Stop conditions

Do not promote any downstream claim past the evidence available for that exact step. In particular:

- historical materialization is not current exact-byte possession;
- archive-index inclusion is not recovered file content;
- a derived report is not the original provider file;
- a provider event is not a session identity;
- a session identity is not a physical device identity;
- a device/model string is not a unique physical handset;
- a device identity is not proof of control by a particular person;
- control is not authorization;
- authorization state is not human attribution;
- `not found in current query` is not `never existed`.

## Validation rule

Use the minimum environment necessary to support the claim. Host/session evidence is sufficient for environment-independent software behavior; Android fixtures may support Android-specific logic; genuine handset execution is required only for device-origin claims.
