# AIxCC Defensive Repair Foundation v1

Status: FOUNDATION / DEFENSIVE-ONLY

## Objective

Adapt reusable AI Cyber Challenge engineering patterns into Centinal26 without creating a second control plane or granting arbitrary offensive authority.

Canonical lifecycle:

`authorized source -> analyze -> candidate finding -> reproduce -> candidate patch -> rebuild -> reproduce -> regression -> independent verification -> evidence -> controlled promotion`

A candidate finding is not a verified vulnerability. A generated patch is not a verified repair. Generation and certification remain separate trust domains.

## Authority boundary

Initial capability vocabulary:

- `software.audit` — analyze an explicitly authorized local/repository artifact and emit candidate findings.
- `software.reproduce` — run a bounded, declared reproducer against an authorized fixture.
- `software.repair` — generate a candidate patch for a reproduced defect.
- `software.verify` — independently verify source identity, reproducer result, patch, build/tests, regressions, postconditions, and evidence hashes.

Not authorized by this foundation:

- arbitrary remote shell;
- arbitrary Internet target acquisition/scanning;
- credential harvesting;
- persistence on third-party systems;
- exploit deployment;
- bypass of Centinal26 authorization or verification gates;
- automatic promotion of an analyzer's own output.

## Upstream resource manifest

The following resources were verified from public upstream material on 2026-08-22. Before executable reuse, pin an exact commit/release and independently record its license and content identity.

| Resource | Upstream | Observed purpose | Integration candidate |
|---|---|---|---|
| AIxCC Competition API | `AIxCyberChallenge/competition-api` | packages challenges, accepts submissions, tests them through a job pipeline | submission/test lifecycle semantics |
| AIxCC cAPI | `aixcc-public/capi` | validates vulnerability-discovery submissions using commit, triggering input, sanitizer and harness identity | deterministic reproduction/evidence contract |
| AIxCC CRS sandbox | `aixcc-public/crs-sandbox` | competition sandbox infrastructure | isolation reference |
| Team Atlanta Atlantis | `Team-Atlanta/aixcc-afc-atlantis` | finalist CRS; automated discovery/analysis | architecture study only initially |
| Trail of Bits Buttercup | `trailofbits/afc-buttercup` | finalist CRS with orchestrator, patcher and program-model components | patch/orchestration study |
| Theori AFC archive | `theori-io/aixcc-afc-archive` | finals CRS snapshot | architecture/evaluation study |
| SIFT Lacrosse | `siftech/afc-crs-lacrosse` | multi-agent fuzzing + symbolic reasoning CRS | analyzer composition study |
| 42-b3yond-6ug BugBuster | `42-b3yond-6ug/42-b3yond-6ug-crs` | finalist CRS snapshot | architecture study |

DARPA reports that all seven finalist CRSs were released as OSI-approved open source and that competition infrastructure, challenges, and documentation were released for continued experimentation. Upstream snapshots may still depend on permissioned services/images or competition-scale LLM budgets, so open source does not imply immediately reproducible or economical operation.

## Promotion states

- `CANDIDATE`: analyzer output only.
- `REPRODUCED`: deterministic bounded reproducer demonstrates the defect in the authorized fixture.
- `PATCH_CANDIDATE`: repair generated but not certified.
- `REGRESSION_PASS`: reproducer no longer demonstrates the defect and declared regression tests pass.
- `INDEPENDENTLY_VERIFIED`: a verifier distinct from the generator validates identities, evidence and postconditions.
- `PROMOTION_ELIGIBLE`: policy permits a branch/PR or other controlled mutation; this state does not itself merge/deploy.

## First benchmark gate

Use intentionally vulnerable or known-ground-truth fixtures only. A benchmark counts as PASS only when all of these hold:

1. source identity is pinned;
2. authorization scope is explicit;
3. a deterministic reproducer fails before repair;
4. the candidate patch is minimal and provenance-linked;
5. the same reproducer passes after repair;
6. declared regression tests pass;
7. verifier is logically separate from patch generation;
8. evidence artifacts are content-addressed/hash-bound;
9. no test, assertion, sanitizer, or verification gate was disabled to manufacture PASS.

## Metrics

Track reproducible true findings, unreproduced candidates/false positives, repair success, regression rate, time to reproduction, time to verified repair, compute/API cost, and human interventions per verified repair.

## Integration rule

Reuse Centinal26 authorization, bounded execution, verification, evidence/audit and state-update primitives. Do not import a finalist CRS wholesale as a new authority plane. Upstream code should enter only after license/provenance review and only where a smaller reusable component materially improves the measured repair loop.
