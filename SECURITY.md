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

## Trust boundaries

The hash chain detects modification but is not a digital signature. A host
administrator can replace both state and code. Future remote attestations must
be additive and must not be represented as implemented until validated.

Never commit credentials, device identifiers, private forensic evidence, or
unredacted account exports.
