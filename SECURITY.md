# Security model

Centinal26 treats automation as authorized state transition, not unrestricted
command execution.

## Enforced baseline

1. A submitted job names a registered capability.
2. A grant must match that capability and remain unexpired.
3. Input is structured JSON; the core does not accept shell source.
4. State transitions persist in SQLite.
5. Audit events form a SHA-256 hash chain.
6. Failed and rejected jobs remain evidence; they are not erased.

## Pinning is identity, not benignness

A SHA-256 pin proves only that the observed bytes equal the bytes that were
pinned. It does not prove that the pinned artifact is safe, non-adversarial, or
appropriate to execute. A malicious or compromised artifact can be perfectly
hash-pinned.

Therefore external executable artifacts pass two independent gates:

1. **Identity gate** — exact expected digest.
2. **Behavior gate** — safe archive structure plus static behavior review before
   extraction or execution.

Labels such as `test`, `PIN test`, `qualification`, `health check`, `bootstrap`,
`vibe test`, or `validation` do not reduce the behavior gate. The gate evaluates
what code can do, not what the file or prompt calls itself.

High-risk indicators include remote-download-and-execute chains, credential or
PIN access, persistence, privilege escalation, destructive filesystem or block
device operations, obfuscated dynamic execution, reboot/device-setting changes,
and arbitrary subprocess or shell execution. A security denial cannot be
automatically overridden by the artifact being evaluated or by a remote job.

## Autonomous-agent boundary

Open-source or proprietary AI agents are untrusted proposers. Agent output does
not become authority merely because an agent is locally installed, open source,
uses a second reviewer, or reports success.

The controlled-evolution path uses these defaults:

- agent proposal mode is patch-only;
- candidate agents do not receive shell/filesystem tools during proposal;
- locked goal tests and security policy are read-only to candidates;
- patches may modify only explicit allowlisted prefixes;
- each changed tree is independently audited before candidate code is executed;
- evaluation runs with a scrubbed environment and no inherited application
  credentials supplied by the controller;
- candidate/test side effects that alter the audited worktree invalidate the
  candidate;
- promotion requires measured improvement over the current parent;
- promotion advances only an `evolution/<goal>/...` branch, never `main`;
- failures and rejected mutations remain evidence.

Model-based security reviewers are defense in depth, not a fail-closed trust
root. If a framework's reviewer can fail open, Centinal26 still applies its own
independent deterministic gate.

## Trust boundaries

The hash chain detects modification but is not a digital signature. A host
administrator can replace both state and code. Static analysis reduces risk but
is not a proof of non-malicious behavior. A normal user-space process is not a
hard sandbox merely because its current working directory is an isolated Git
worktree. High-risk candidate execution should use an ephemeral or otherwise
contained environment with no production credentials or sensitive mounts.

Future remote attestations must be additive and must not be represented as
implemented until validated.

Never commit credentials, device identifiers, private forensic evidence, or
unredacted account exports.
