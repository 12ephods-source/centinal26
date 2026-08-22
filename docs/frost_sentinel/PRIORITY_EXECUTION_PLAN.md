# Frost Sentinel Priority Execution Plan

Date: 2026-08-22

1. **Provider-anchor join:** use exact event/notification anchors to request or correlate session creation/refresh, IP, user-agent, provider device/session IDs, token state, and internal audit keys.
2. **Cross-snapshot recovery:** recover Takeout A/C, then cryptographically inventory and diff A/B/C.
3. **Device resolution:** map unresolved Android configuration identifiers and test stable joins to provider anchors.
4. **Claim-scoped handset validation:** execute device collection only where a claim requires live-device provenance.
5. **Trusted-provenance comparison:** compare handset files/configuration against known-good upstream sources, not only a current baseline.
6. **Authorization adjudication:** classify each disputed event as authorized / unauthorized / unknown from evidence.
7. **Attribution gate:** only after session/device/control/authorization joins are satisfied, evaluate human attribution with independent corroboration.

## Stop conditions

Do not promote any downstream claim past the evidence available for that exact step. In particular:

- a provider event is not a session identity;
- a session identity is not a physical device identity;
- a device identity is not proof of control by a particular person;
- control is not authorization;
- authorization state is not human attribution.

## Validation rule

Use the minimum environment necessary to support the claim. Host/session evidence is sufficient for environment-independent software behavior; Android fixtures may support Android-specific logic; genuine handset execution is required only for device-origin claims.
