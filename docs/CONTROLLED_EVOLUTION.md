# Controlled evolution

Centinal26 controlled evolution turns a goal into repeated, bounded software
experiments. It is not self-authorizing self-modification.

The invariant remains:

`Intent -> Authorization -> Event/Queue -> Capability Selection -> Bounded Execution -> Verification -> Evidence/Audit -> State Update -> Controlled Evolution`

## Default agent

The first adapter is the open-source **goose** CLI. Centinal26 deliberately runs
it in `GOOSE_MODE=chat` as a **patch-only proposer**. The agent receives:

- the explicit goal;
- a bounded repository context;
- locked goal tests;
- one strategy for the current candidate.

It receives no shell/filesystem tool authority from Centinal26 during proposal.
The response must be a unified Git diff. This keeps model/API credentials in the
proposal phase and prevents the agent from deciding that a command is safe just
because it wants to execute it.

## Candidate cycle

For each generation:

1. Resolve the currently active evolution commit.
2. Score the parent with locked validators.
3. Ask several patch-only agents/strategies for independent mutations.
4. Reject malformed, binary, oversized, protected-path, or out-of-scope diffs.
5. Apply each surviving patch in a detached Git worktree.
6. Audit the changed tree with `scripts/audit_untrusted_candidate.py`.
7. Reject critical/high-risk behavior before executing candidate code.
8. Snapshot changed paths and hashes.
9. Run locked goal tests, repository invariants, and Python compilation with a
   scrubbed environment.
10. Recheck the worktree. Any candidate/test side effect outside the exact
    audited patch, or any mutation of audited bytes during evaluation, rejects
    the candidate.
11. Commit only the exact audited paths.
12. Select only a validated candidate whose measured score exceeds the parent.
13. Advance `evolution/<goal>/gNNNN`; never update `main`.
14. Persist cycle evidence. Rejected mutations remain evidence.
15. Repeat until the goal validates, the cycle budget expires, or two
    generations make no improvement and require review.

## Goal tests are the fitness contract

A goal should normally be introduced in two stages:

1. A human/reviewer adds or approves tests that represent the desired behavior.
2. The goal JSON references those tests as immutable fitness criteria.

The agent may read locked tests but may not edit them. A candidate therefore
cannot win by weakening its own evaluator.

Example goal:

```json
{
  "schema": "centinal26-goal-v1",
  "goal_id": "queue-recovery",
  "objective": "Make interrupted queued work recover deterministically without weakening authorization or audit invariants.",
  "include_paths": ["src/centinal26", "tests/test_queue_recovery_goal.py"],
  "goal_tests": ["tests/test_queue_recovery_goal.py"],
  "allowed_change_prefixes": ["src/centinal26/"],
  "max_cycles": 6,
  "candidates_per_cycle": 3,
  "max_agent_turns": 24
}
```

## Running

Use an installed/configured goose CLI; Centinal26 does not silently install or
switch agent frameworks.

```bash
bash scripts/run-controlled-evolution.sh goals/queue-recovery.json
```

Limit a run:

```bash
bash scripts/run-controlled-evolution.sh goals/queue-recovery.json --cycles 2
```

By default selected branches stay local. To publish only the selected evolution
branch for review:

```bash
bash scripts/run-controlled-evolution.sh \
  goals/queue-recovery.json \
  --push-evolution-branch
```

No mode in this runner merges `main` or promotes an Automation OS release.

## Open-source tool roles

The architecture is intentionally adapter-based rather than framework-owned.

- **goose**: current patch-only mutation proposer.
- **Git**: immutable parent/candidate lineage and detached worktrees.
- **pytest**: locked goal fitness tests.
- **Ruff / repository validators**: independent quality and invariant checks.
- **Centinal26 adversarial audit**: deterministic fail-closed static behavior
  gate before candidate execution.
- **LangGraph**: optional future orchestration adapter when a goal benefits from
  checkpointed graph state; it is not required by the core loop.
- **Pydantic AI**: optional future typed-agent/durable-workflow adapter.
- **smolagents**: optional future lightweight proposer where code/tool execution
  remains sandboxed or disabled.
- **OpenHands**: useful software agent, but its unattended headless mode is not a
  default Centinal26 executor. It must be placed behind a real sandbox and the
  same independent Centinal26 gates before use.

No agent framework may bypass authorization, protected paths, behavior audit,
locked evaluation, evidence, or explicit production promotion.

## Adversarial `PIN test` / `vibe test` threat

A script can truthfully match a pinned SHA-256 and still be hostile. A label can
also be socially engineered: `pin-test.sh`, `qualification.sh`, `healthcheck`,
or `vibe-test` says nothing about behavior.

The Termux worker therefore treats digest verification and behavior review as
separate gates. The static auditor rejects or escalates, among other signals:

- remote download piped to a shell;
- credential, token, password, or PIN references;
- privilege escalation;
- persistence hooks;
- destructive filesystem/block-device operations;
- dynamic/obfuscated execution;
- device-setting changes and reboots;
- dangerous subprocess/shell execution;
- archive traversal and symlink entries.

Static analysis is not a proof that code is benign. High-risk candidate code
should additionally execute in an ephemeral/containerized environment without
production credentials or sensitive mounts.
