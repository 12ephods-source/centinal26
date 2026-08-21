# Automation OS / Frost Forge Project Consolidation

Version: 2.7
Status: CANONICAL / HOST_V1_VERIFIED_COMPLETE / RUNTIME_GOVERNANCE_ENFORCED / OUTBOUND_CONTROL_SOFTWARE_VERIFIED / PHYSICAL_AND_DEPLOYMENT_GATES_EXTERNAL
Repository: `12ephods-source/centinal26`
Canonical branch: `main`
Observed integrated production head: `34ba2f86ef224b3eeaafb96c3c152593dc2b41f6`
Runtime-governance validation head: `427f8e884352839e11fcd99cfcdd51643fb1f2ab`
Qualified physical-commissioning source: `9c0925ee7e3dc23f6e81718f9c1a2ca7926ec483`

## Source of Truth

Primary evidence is Git history, exact-head CI, durable workflow ledgers, immutable artifacts, explicit external-gate issues, Base44 physical-gate records, and live connector observations. This file is the canonical human continuation authority; `automation/PROJECT_STATE.json` is the machine continuation state; `PROJECT_STATE_AUTOMATION_OS.md` is the concise summary.

## Terminal Objective

Operate a reusable evidence-centered automation platform that converts project intent into bounded execution, independent verification, persistent evidence, reusable capabilities, integrated features, and release candidates while preserving authorization, recovery-root, physical-validation, persistence, provenance, deployment, and connector boundaries.

## Canonical Pipeline

`Intent -> Authorization -> Event/Queue -> Capability Selection -> Bounded Execution -> Verification -> Evidence/Audit -> State Update -> Controlled Evolution`

## Verified Host State

The canonical host/runtime system includes Frost Master Project Protocol v3, deterministic governance, autonomous question resolution, Project Productizer -> Judge E2E validation, bounded multi-role execution, durable execution evidence, executor contracts, the universal Termux installer, fail-closed module management, exact-source-bound Android evidence capture, controller enrollment verification, canonical enrollment digest, worker heartbeat verification, one-run physical commissioning, normalized device-profile evidence, outbound worker startup, authenticated bounded controller polling, and a deployable Vercel controller target.

PR #220 is the runtime authority boundary. Every mutating or consequential task must resolve immutable canonical references for the authorized objective, authorization evaluation, and Guardian-issued capability token. Inline task claims are not authority. Missing, stale, malformed, superseded, or over-broad authority fails closed before execution. PR #220 exact head `427f8e884352839e11fcd99cfcdd51643fb1f2ab` passed `validate`, `CI`, `automation-gates`, `federation-gates`, `Mature Product Qualification`, `Executor Integration Validation`, and `hard-sandbox`.

PR #226 reconciles executor truth without collapsing validation boundaries: local Python/repository executors are host-integration verified; API connector execution is host-integration verified with live target authorization separate; the agent plane is host behavioral/integration verified; Android is host-contract verified and still awaits genuine physical-worker evidence.

## Physical Qualification

Issue #208 is the canonical physical gate. PR #225 hardened the commissioning path with normalized Android/Termux device-profile evidence, exact source binding, internally consistent hashed profile/report data, and guidance-only treatment of the superseded RC9 workflow.

PR #225 exact head `e062fd3364e7c3219a79263b68825df928fe545f` passed CI, Automation Validation, `validate`, automation-gates, federation-gates, and Mature Product Qualification. Its merged qualified source is `9c0925ee7e3dc23f6e81718f9c1a2ca7926ec483`.

### Phase A — DEVICE_VALIDATED

`one pinned Android/Termux commissioning run -> preserve combined ZIP -> controller verification against 9c0925ee... -> observe/register Android worker -> one harmless bounded Android work item -> preserve event/lease chain and independent Judge evidence`

A controller commissioning PASS establishes eligibility only. Real workload evidence remains required.

### Phase B — PERSISTENT_VALIDATED

`preserve pre-reboot identity/evidence -> physically reboot phone -> require changed boot_id -> worker/controller return -> fresh verified heartbeat -> valid lease/event chain -> one harmless post-reboot bounded work item -> independent Judge evidence`

Remote reboot and host/simulation substitution do not satisfy this gate.

## Outbound Android Worker

PR #218 inverted the control plane so commissioned Android/Termux workers initiate outbound HTTPS rather than requiring inbound SSH/ADB. The worker starts under Termux:Boot, uses a closed diagnostic capability set, exact device/source targeting, expiry and nonce replay rejection, HMAC-SHA256 job/result authentication, bounded backoff, restrictive credential permissions, and an append-only hash-chained journal. Arbitrary remote shell and controller-provided executable text are explicitly absent.

PR #221 added the authenticated controller queue. The controller registers commissioned devices, emits only closed capabilities, signs expiring device-targeted jobs, rejects unknown devices and arbitrary capabilities, verifies signed results, and acknowledges idempotently.

## Vercel Controller

PR #224 added the initial Vercel Functions deployment target. PR #227 then made the deployment path self-contained around first-party Vercel services where possible:
- preferred private Vercel Blob state with Redis fallback;
- encrypted per-device credentials;
- one-time provisioning tokens;
- authenticated and replay-protected polling;
- bounded admin enqueue;
- signed result verification;
- dedicated Node/Vercel controller validation;
- an idempotent post-merge workflow capable of creating/linking `frost-forge-controller`, generating controller secrets without printing them, creating a private Blob store, deploying production, and verifying `/api/health` when an authorized GitHub `VERCEL_TOKEN` exists.

PR #227 exact head `347b5773bfedf80013e8286745368ff62ed9a3e2` passed Vercel Controller Validation plus CI, Automation Validation, `validate`, automation-gates, federation-gates, and Mature Product Qualification before merge as `e36ddbafec46d0a5d7da29b40633db5476a34a48`.

PR #229 adds sanitized bootstrap observability to issue #228. Its exact head `09ac1ffaea3d3b6188f01941ad562a513124fd28` passed all triggered standard qualification suites before merge as current production head `34ba2f86ef224b3eeaafb96c3c152593dc2b41f6`.

The resulting bootstrap ledger is decisive: workflow run `32497973290` observed `VERCEL_TOKEN present=false`; Vercel CLI/auth/project/link/secret/Blob/deploy/health steps were skipped; no deployment URL exists. Therefore:

`VERCEL_CONTROLLER = VERIFIED_SOFTWARE_DEPLOYMENT_BLOCKED_CREDENTIAL`

This is not a controller-code failure. The connected Vercel team `ETE` currently reports zero projects. The exposed connected Vercel actions provide authenticated reads but no project-create or personal-token-create action; the generic deploy wrapper does not expose the arguments required to materialize the project. The OAuth credential used by the connected tool is not exportable as a GitHub Actions secret.

Issue #228 is the canonical deployment gate. Reopen execution when an authorized Vercel deployment credential becomes available to GitHub Actions or another supported project-create/deploy surface becomes available.

## Connector Gate

Issue #209 remains the operation-specific connector matrix. GitHub has verified live read/write in the authorized Centinal26 scope. Gmail, Google Calendar, and Google Drive have bounded reversible live-write evidence. Google Contacts remains authenticated read/search with no reversible write operation exposed. Vercel has authenticated read access but its create/deploy credential boundary is tracked separately in issue #228.

## Mandatory Distinctions

- queued != executed != verified;
- installed != authorized;
- host PASS != physical-device PASS;
- software deployment target ready != live deployment;
- authenticated connector access != exportable deployment credential;
- objective proposal != authorized objective;
- independent Judge verification != objective authorization != capability-token scope;
- physical commissioning eligible != bounded worker task PASS;
- device validated != persistent validated;
- captured evidence != verified enrollment != active worker;
- reversible write verification != unrestricted connector authority;
- absence of observed evidence != evidence of absence.

## Current Critical Path

Physical release path:

`commission real Android device at 9c0925ee... -> controller commissioning verification -> bounded Android worker task -> physical reboot -> verified worker return -> post-reboot bounded task -> evidence-gated final release decision`.

Unattended outbound-operation path:

`authorized Vercel deployment credential or equivalent supported project-create surface -> materialize frost-forge-controller -> private Blob state -> production deploy -> /api/health READY -> provision commissioned device -> outbound bounded work`.

Continue every independent bounded workstream automatically. Stop only at verified completion or a genuine physical/external, authorization/platform, falsification, supersession, or negative-value boundary.
