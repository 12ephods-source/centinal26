# Defensive Repair Threat Model v1

## Protected properties

- authorization cannot be expanded by analyzer output;
- candidate repair cannot certify itself;
- source, repair, and patch identities remain provenance-bound;
- regressions prevent promotion;
- malformed or altered evidence fails closed;
- repository CI success is not treated as device or scientific validation.

## Adversarial cases

| Case | Required behavior |
|---|---|
| Unauthorized fixture ID | reject before analysis |
| Expanded authorization scope | reject before analysis |
| Altered original source | reject/fail verification |
| Altered repaired source | fail repair identity |
| Tampered patch | fail patch identity |
| Repair clears reproducer but breaks normal behavior | fail regression gate |
| Analyzer claims success without verifier evidence | remain candidate/unverified |
| Nondeterministic canonical evidence | qualification failure |
| Attempted arbitrary source/network/shell authority | unsupported by capability contract |

## Current containment

The v1 capability executes only a repository-owned Python fixture through a restricted builtins namespace. It does not accept arbitrary source input and exposes no network, credential, exploit-deployment, or shell interface. General repository execution is explicitly outside this capability version and requires a separate sandbox/authorization design.
