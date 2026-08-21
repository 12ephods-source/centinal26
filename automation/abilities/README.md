# Frost Forge Reusable Ability Registry

## Standing rule

When a requested capability is unavailable, do not stop at a narrative limitation if a safe bounded implementation is possible.

Use this sequence:

1. **Discover** existing built-in, connected, repository, and registered capabilities.
2. **Build** the smallest bounded tool/adapter only when the missing capability can be implemented within current authorization and platform limits.
3. **Test** it with deterministic checks or an independent verification path appropriate to its risk.
4. **Run** it on the intended bounded task when execution is authorized and available.
5. **Register** the reusable tool as an ability with source, interface, verification, provenance, status, and rollback/removal information.
6. **Reuse before rebuilding** on later tasks.
7. If authentication, physical-device access, platform controls, safety policy, or another real authority boundary prevents implementation/execution, record the exact blocker and continue independent work. Never fabricate execution or bypass the boundary.

## Registry semantics

`automation/abilities/registry.json` is the machine-readable catalog. Registration records discovery and reuse metadata; it does **not** grant additional authority.

Each ability requires:

- `id`: stable lowercase machine identifier using letters, digits, `.`, `_`, `/`, or `-`.
- `name`: concise human name.
- `kind`: tool, adapter, verifier, collector, runner, or other bounded capability class.
- `source`: non-empty repository path/commit/artifact identity object.
- `interface`: non-empty invocation contract and input/output shape object.
- `verification`: non-empty tests, CI, independent checks, or physical evidence object as applicable.
- `provenance`: non-empty origin and lineage object.
- `lifecycle`: non-empty object containing at least one explicit `rollback` or `removal` path.
- `status`: `EXPERIMENTAL`, `VERIFIED`, `SUPERSEDED`, or `BLOCKED`.

The registry document itself is schema- and policy-validated before registration. A new entry is validated both before and after insertion, duplicate IDs fail closed, and the updated registry is written by atomic replacement so an interrupted normal write does not leave a partially serialized registry.

A registered ability remains subject to the same authorization, evidence, side-effect, and physical-vs-host boundaries as any other executor.

## CLI

```bash
python scripts/ability_registry.py validate
python scripts/ability_registry.py list
python scripts/ability_registry.py register path/to/ability.json
```

Registration is append-only by stable `id`; replacement requires an explicitly versioned successor rather than silently overwriting prior evidence.
