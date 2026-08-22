# Physical-Boundary Improvement Cycle

This is the reusable Frost Forge / Automation OS continuation pattern for work that is host-qualified but still requires authentic Android/Termux execution.

## Physical-boundary pattern

1. Reuse the existing bounded worker/control-plane architecture before adding another execution plane.
2. Reuse one deterministic, resumable device-handoff runner rather than extending host-only machinery.
3. Checkpoint only the minimum irreducible Android authorization step. Never fabricate or infer authorization.
4. Resume automatically after that checkpoint through: environment verification -> dependency installation -> non-destructive qualification -> one bounded real workload -> device-origin evidence -> independent verification.
5. Never substitute host, CI, emulator, session, simulation, or cross-device evidence for authentic physical-device evidence.
6. Preserve distinct lifecycle states: built -> host-tested -> device-executed -> device-verified -> persistent-verified.
7. Preserve failed and superseded attempts as provenance.

## Improvement cycle

For high-value capabilities use:

`OBSERVE -> MEASURE -> HYPOTHESIZE -> COMPARE -> CRITICIZE -> IMPLEMENT -> TEST -> VERIFY -> RECORD -> REPEAT`

A failed iteration is evidence. Classify the failure, preserve it, patch only the demonstrated cause, and rerun a fresh bounded test instead of restarting planning from zero.

Stop only when no demonstrated higher-value safe improvement remains or a genuine authorization, physical-device, platform, or safety boundary is reached.

## Destructive Library-cleanup invariant

Use:

`exact item -> local download -> separate archive -> SHA-256 ledger -> exact re-identification -> authenticated UI delete -> post-delete absence verification -> evidence package`

The first physical proof remains capped at one deletion. The canonical physical-boundary solver ends that proof disarmed pending review; unattended operation is a separate promotion decision.

## Test-design rule

Host regressions must test the boundary itself, not simulate physical success. At minimum they should execute the solver's host self-test and host run path and verify that neither can emit a physical-success state. Static tests should additionally preserve the one-delete limit, explicit disarm, evidence packaging, and absence of arbitrary remote shell behavior.

## Reuse trigger

Apply this pattern automatically when the remaining state is equivalent to device action required, physical evidence missing, host-qualified but phone-unverified, Android/Termux worker not observed, or real-device validation required. Re-plan the architecture only if the physical or authorization model materially changes.
