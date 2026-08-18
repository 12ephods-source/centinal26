# FToE Autonomous Research Orchestrator

Status: DRAFT / REVIEW. Do not deploy the legacy direct-network daemon to Termux.

## Current architecture

The supported path is split-authority:

`runit/Termux supervisor -> deterministic local gates`

`runit/Termux supervisor -> one-shot provider broker -> outbound LLM API`

The resident supervisor (`scripts/ftoe_secure_supervisor.py`) has no HTTP client and does not parse provider credentials. The one-shot broker (`scripts/ftoe_provider_broker.py`) owns outbound HTTPS and provider credentials, but has no subprocess execution, GitHub mutation, publication, or scientific-state promotion capability. Provider responses are treated as hostile data and schema-validated before arbitration.

This is **process separation, not OS privilege separation**. Ordinary Termux processes share the same Android application UID; therefore the supervisor and broker are not a hard sandbox against a malicious process running under that UID. The split reduces accidental authority aggregation and credential exposure but does not replace Android/OS isolation.

## Credential policy

Provider credentials are stored in `~/.config/ftoe-research/providers.secrets` with mode `600`. The file uses literal `KEY=VALUE` records and is parsed by the broker; it is never sourced or evaluated by the shell. The long-lived service receives only the path to the file, not the credential values in its environment.

No provider key may be written to GitHub, cycle artifacts, logs, prompts, state JSON, command-line arguments, or deterministic gate output.

## Sister-agent attack strategy

Each cycle targets exactly one highest-priority non-PASS publication gate. Independent providers are assigned blind attack modes and do not receive other agents' verdicts before their own result is sealed:

1. formal derivation;
2. counterexample construction;
3. numerical-stability / hidden-fit attack;
4. evidence-independence / circularity audit;
5. hostile-referee falsification design.

A FAIL is preserved. REVIEW blocks promotion. PASS requires valid local evidence identifiers from the evidence packet. Cross-model agreement cannot promote a deterministic publication gate.

## Security attack tree

Before phone deployment, the architecture must survive these failure classes:

- credential exfiltration from environment, logs, prompts, artifacts, or shell evaluation;
- prompt-injection attempts to obtain arbitrary execution, GitHub mutation, publication, or policy change;
- malicious provider output containing fabricated evidence references;
- broker compromise attempting subprocess execution;
- supervisor compromise attempting direct outbound HTTP;
- stale/legacy service files launching the direct-network daemon;
- repeated network/auth failures causing uncontrolled retries or cost growth;
- same-UID limitation being misrepresented as hard isolation.

A security PASS requires deterministic regression tests for the enforceable boundaries and an explicit REVIEW/limitation record for boundaries that ordinary Termux cannot hard-enforce.

## Plateau control

If the same gate and evidence digest persist, the controller changes strategy rather than repeatedly purchasing the same review:

- normal review;
- falsifier design;
- deterministic escalation with a reduced LLM-call budget.

## Execution boundary

Local execution remains an explicit Python argument-vector allowlist. No arbitrary shell string, root, ADB, Android Accessibility, package-management authority, merge authority, or publication authority is exposed to an LLM.

## Publication and deployment boundaries

Publication readiness is fail-closed. It requires all deterministic gates to succeed, every mandatory publication gate to be PASS, a claim ledger, and a publication draft. LLM consensus is advisory only.

Phone deployment is separately fail-closed in `physics/ftoe/publication_gate.json`. A publishable physics state does not automatically authorize installing the daemon, and a secure daemon does not promote scientific claims.

## Legacy path

`scripts/ftoe_research_daemon.py` is retained only for historical comparison while PR #108 is draft. The installer now launches `scripts/ftoe_secure_supervisor.py`; the legacy direct-network daemon must not be used for Termux deployment.

## Deployment state

The split-authority architecture is implemented but **not yet approved for phone deployment**. PR #108 remains draft. Acceptance requires the dedicated split-authority tests plus review of the repository-level `CI`, `automation-gates`, `federation-gates`, and `Mature Product Qualification` checks. A green dedicated orchestrator workflow alone is insufficient.
