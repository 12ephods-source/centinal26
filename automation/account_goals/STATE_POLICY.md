# Account Goal State Transition Policy

Goal states are evidence claims, not labels of convenience.

Allowed forward transitions normally follow:

`PROPOSED -> IMPLEMENTED -> TESTED -> CI_VERIFIED -> INDEPENDENTLY_VERIFIED`

Then, where applicable:

`SOFTWARE_RELEASE_COMPLETE -> DEVICE_TESTED -> PERSISTENCE_VERIFIED -> DEPLOYED_APP_COMPLETE -> PRODUCTION_READY`

`BLOCKED_EXTERNAL` may coexist with progress on independent goals and must be exited only when the external dependency is actually resolved. `FAILED` and `REGRESSED` preserve the failed evidence and require a versioned repair; they are never overwritten as if failure did not happen. `SUPERSEDED` preserves lineage and points to a verified successor.

Promotion requires evidence satisfying that goal's `success_criteria`. Demotion is mandatory when a previously required invariant becomes false. Host/CI results cannot promote device-specific states. Transaction/revenue claims require transaction evidence. Scientific claims retain their domain-specific epistemic gates regardless of software state.
