# Centinal26 Full-Autopilot Conversation Consolidation

## Project classification
**Automation** is the primary project. Physics is a major workload executed through the automation system, and cybersecurity hardening is explicitly deferred until the cybersecurity phase except for lightweight integrity/recovery safeguards.

## Suggested conversation name
**Centinal26 Full Autopilot: Termux Execution Plane, Evidence Provenance, and Autonomous Project Reconciliation**

## Exact conclusion
This conversation converged on a full-autopilot operating model: the user instructed ChatGPT/Centinal26 to act as the operational stand-in for routine project work, not merely as a CI watcher. Autopilot should reconcile live state, infer priorities, select and chain available authorized tools, execute, test, criticize, improve, independently verify, preserve evidence/provenance, recover from failures, update canonical state, and immediately continue to the next useful action.

GitHub remains the durable source of truth for code/PR/CI state. The canonical Android/Termux daemon is the physical execution plane when an authentic worker is available. Evidence ownership is USER_EVIDENCE, while provenance/origin is tracked separately. Lifecycle promotion is restricted to attempted -> built -> sandbox-tested -> device-tested -> production-ready, with device-tested requiring genuine device-origin evidence plus independent verification.

Old work is preserved. Superseded PRs were closed only after compact reconciliation or replacement; legacy branches/history were not intentionally deleted.

## Major implemented outcomes
- Canonical persistent Termux daemon and code-gate architecture merged into Centinal26.
- Automatic code-trigger policy: created/edited programs are qualified, tested, improved, run when authorized/available, verified, and evidenced.
- Blocked items converted from terminal states into repair/fallback/watch-resume workflows.
- Evidence ontology corrected: USER_EVIDENCE ownership is separate from execution origin.
- Restrictive cybersecurity governance deferred to the cybersecurity phase to avoid blocking engineering progress.
- Multiple stale PR chains reconciled into compact current-main successors while preserving scientific PASS/FAIL/REVIEW states.
- Full-autopilot controller broadened from CI/PR handling to project-level prioritization and cross-tool execution.
- Capability-fabric policy added: use currently installed, connected, authorized, relevant capabilities through one canonical controller.
- Legacy branch deletion explicitly avoided.

## Unique insight contributed to the group goal
The critical architectural insight is that autonomy quality is determined less by how many tools are connected than by the decision loop that chooses what to do next. The system should optimize verified decision value, not activity. Negative scientific results are first-class progress because they reduce the hypothesis space. A useful autonomous system must combine evidence-preserving execution with dynamic prioritization.

## Ranked problems and best current solutions
1. **Autopilot stops at reporting checkpoints.** Enforce `verify -> next action` in the same loop and persist exact continuation checkpoints.
2. **Automation can optimize low-value housekeeping instead of goals.** Use a live dependency/work graph scored by information gain, downstream unlock, value, labor reduction, success probability, cost, risk, and reversibility.
3. **Authentic Termux/device evidence can be confused with other user-owned evidence.** Separate `owner_class=USER_EVIDENCE` from `origin_class`; device claims require authentic Android/Termux provenance.
4. **Stale divergent PR stacks accumulate.** Use compact current-main reconciliation successors preserving exact heads, verdicts, hashes, and unique artifacts rather than bulk-merging stale ancestry.
5. **Code is written but not executed/tested.** Trigger automatic code qualification: static checks -> tests -> bounded improvement -> execute -> verify -> evidence.
6. **Recoverable blockers stop global progress.** Classify blocker, repair/fallback/watch-resume, continue independent work, deduplicate retries, preserve failed evidence.
7. **Security controls impede pre-security engineering.** Defer restrictive governance until cybersecurity phase; retain low-friction integrity, rollback, secret hygiene, hashes, and evidence safeguards.
8. **Old work may be lost during consolidation.** Close/supersede PRs only after preservation; do not delete branches/history by default.
9. **Capability sprawl creates competing controllers.** Use a provider-neutral capability registry under one canonical state machine; capabilities are adapters, not independent authorities.
10. **Scientific failures can be mistakenly repaired.** Freeze thresholds and keep software PASS, numerical compatibility, empirical support, and theory confirmation epistemically separate.

## Remaining questions
- When will an authentic Android/Termux worker be available for physical device qualification?
- Which current-main implementation should become the canonical live priority ledger/work graph?
- Which stale Automation capabilities (#100 export bridge, #98 Wordbook, #89 conversation/Termux loop, etc.) remain uniquely valuable after current-main reconciliation?
- Which scientific unresolved dependency has the highest information gain after current SO(10)/protected-I reconciliations?
- When should the project explicitly enter the cybersecurity-hardening phase?
- Which externally connected services still require interactive OAuth/consent and therefore remain CONNECT_PENDING?
