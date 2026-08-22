# Cybersecurity + Automation Unified Integration

## Ownership
Cybersecurity / Frost Sentinel remains the evidentiary project owner. Automation / Centinal26 is embedded as the bounded control, execution, verification, persistence, and update layer.

## Canonical flow
`Cybersecurity intent/evidence state -> authorization -> Automation capability selection -> bounded execution -> independent verification -> Cybersecurity evidence/audit -> canonical state -> paired updater`

## Epistemic boundary
Automation output is not primary evidence merely because it was generated automatically. Provider records, acquired originals, hashes, physical-device output, testimony, inference, authorization, and attribution retain separate evidence classes.

## Pair update transaction
1. Lock the update cycle.
2. Require clean Git worktrees.
3. Fetch both configured remotes.
4. Reject local-ahead/diverged histories.
5. Preflight both projects before changing either.
6. Apply fast-forward-only updates.
7. Roll back a partial pair update when safe.
8. Refresh Automation -> Cybersecurity integration snapshot.
9. Export only non-evidentiary Cybersecurity shared state toward Automation.
10. Seal the update receipt and manifests with SHA-256.

## Protected Cybersecurity content
The updater never cross-copies top-level `evidence`, `primary`, `acquired`, `vault`, `cases`, `originals`, or `forensic_images` into Automation.

## Validation classes
Host syntax/integration validation and Android/Termux physical validation remain separate. A successful host updater test does not prove handset execution.
