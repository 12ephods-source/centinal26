# HERMES + C05 Frost Agent Fabric Integration

This component consolidates the recovered HERMES/Frost architecture so HERMES owns reasoning, model/provider coordination, native MoA, relay UX, and workspace/transcript handling while C05/Centinal26 owns consequential execution semantics.

## Architecture

```text
HERMES
  reasoning / provider configuration / MoA / relay
        |
        v
Hermes C05 bridge
  exact capability identity
  request hashing
  one-time direct-user grants
  immutable connected-request staging
  bridge audit chain
        |
        v
C05 / Centinal26
  authorization
  durable queue
  bounded worker execution
  independent verification
  audit / provenance
```

The same HERMES/model component does not gain authority to authorize arbitrary operations, execute unrestricted scripts, verify its own execution, or write to the connected GitHub provider.

## Automatic model-callable surface

Local C05:

- `system.echo`

Connected GitHub request staging:

- `system.health`
- `system.capabilities`
- `frost.diagnostics.echo`
- `frost.diagnostics.sha256`
- `frost.diagnostics.canonicalize`

The GitHub path translates requests into the current provider contract and stores them locally. It deliberately performs no GitHub mutation.

## Non-A0 flow

Non-A0 local capabilities require a direct-user, capability-bound, expiring, single-use token issued outside model context:

```bash
hermes-c05 grant CAPABILITY
hermes-c05 call CAPABILITY \
  --json '{"key":"value"}' \
  --user-approve \
  --approval-token TOKEN
```

The Hermes plugin never receives or supplies that direct-user approval channel.

## Script migration

The historical direct-script execution path is retired. `frost_stage_script` exists only as a compatibility migration tool:

```text
proposed code
-> SHA-256
-> inert immutable artifact
-> no authorization
-> no execution
```

Translate intended actions into registered C05 capabilities instead.

## Recovered HERMES lineage

The recovered HERMES Frost Hybrid Termux Monolith v2.0.0 remains the historical base. Recorded identities used by the one-paste integration release are:

- embedded runtime payload SHA-256: `c23d8a1004df13eccfa2fec82835f2bce1274d2aed92a633df49734ca51aef8a`
- later certified whole-shell candidate SHA-256: `322e16d78b8eeb0940e0083f69e9d3720b3b2f383715d9cc180e60ff40c44df9`

These identities are provenance records; absence of the recovered shell on a device is not represented as byte-identical recovery.

## Current C05 baseline

This adapter release was developed against Centinal26 commit:

`22cd324ea56731701670c65037857dfa8c51fc5f`

Provider selection remains explicit. Installing this adapter does not make GitHub Actions, HERMES, Base44, or another provider the universal execution default.
