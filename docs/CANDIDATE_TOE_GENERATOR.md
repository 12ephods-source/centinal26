# Candidate ToE Generator v1

## Provenance

This is a **reconstructed successor**, not a claim of byte-identical recovery of the historical source.

The Automation project record identifies `QuantityTheoryGeneratorAgent` as a historical component intended for AAARD/pluginization. A later reconstruction preserved its core contract: generate a candidate quantitative theory with `PROPOSED` epistemic status, explicit assumptions, and mandatory follow-up checks including dimensions, limiting cases, benchmarking, and falsification.

## Authority boundary

The generator is a hypothesis generator only.

`candidate generation -> PROPOSED -> derivation -> mathematical checks -> numerical benchmarks -> external-data confrontation -> separate validation/promotion`

It cannot mark its own candidate VERIFIED, scientifically valid, canonical, or empirically confirmed.

## API

```python
from centinal26.agents.candidate_toe_generator import generate_candidates

candidates = generate_candidates(
    "Construct a falsifiable framework unifying gravity and quantum matter",
    count=8,
    seed=20260822,
    preference="conservative",
)
```

Preferences are `conservative`, `novel`, `simple`, and deterministic `id` order.

Each result contains:

- deterministic candidate ID and SHA-256 identity;
- component selection for gravity, visible sector, hidden sector, bridge, and quantum frame;
- principles and action terms;
- assumptions;
- mandatory next checks;
- falsifiers;
- prediction domains;
- complexity/novelty scores;
- reconstruction provenance.

## Current search space

The first bounded grammar intentionally favors interpretable, falsifiable combinations over unconstrained prose generation:

- gravity: GR EFT, R^2 gravity, scalar-tensor;
- visible sector: SM baseline or SM + neutrino sector;
- hidden sector: none, Z2 scalar, dark U(1);
- bridges: gravity-only, Higgs portal, kinetic mixing;
- quantum frame: low-energy EFT or explicitly hypothetical emergent-microscopic framing.

Compatibility rules prevent, for example, a Higgs portal without a scalar hidden sector or kinetic mixing without a dark U(1).

## Scientific limitations

This generator does not derive UV completion, anomaly cancellation, renormalization-group closure, naturalness, observational likelihoods, or quantum-gravity consistency. Those belong to downstream validators. Synthetic consistency is not empirical validation.
