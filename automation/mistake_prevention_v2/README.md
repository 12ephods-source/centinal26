# Mistake Prevention V2

This supersedes the mutable-registry-as-authority design.

Authority is the set of content-hashed, append-only event batch files under `events/`. Any human-readable registry, dashboard, spreadsheet, or summary is a rebuildable projection and is explicitly non-authoritative.

Namespaces are separated:

- `account`: verified or reported mistakes from this account/project.
- `peer`: only authorized/shared peer records.
- `public`: only public, sourceable failure reports.

Legacy V1 registry content is historical input only. Migration does not promote a legacy row to VERIFIED.

Controls are separated by enforceability:

- Mechanical guards validate structured evidence/state in instrumented tool and artifact pipelines.
- Review heuristics cover semantic or judgment failures that cannot honestly be represented as deterministic truth gates.

The compact runtime supports:

```bash
python mistake_prevention_v2.py project .
python mistake_prevention_v2.py evaluate .
python mistake_prevention_v2.py preflight request.json
python mistake_prevention_v2.py taint provenance_graph.json bad_claim_id
```

`preflight` is enforceable only where a pipeline actually invokes it. It does not intercept unconstrained model token generation.

Taint propagation follows only explicit provenance edges. Objects outside the instrumented graph remain UNKNOWN rather than being assumed clean or tainted.

Guard evaluation uses holdout/boundary cases rather than simply replaying the example that motivated each guard.

Core rule: lower confidence/status is preferable to unsupported promotion.
