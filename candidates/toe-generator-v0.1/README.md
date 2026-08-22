# Candidate ToE Generator & Tester v0.1

This candidate module composes **structured theory hypotheses** from the surviving Frost Physics evidence registry and evaluates them with fail-closed gates. It is deliberately not a prose theory generator and not a truth-certification system.

## What it does

- freezes component identities before testing;
- keeps falsified historical branches as regression cases;
- excludes falsified branches from default candidate generation;
- distinguishes empirical/null interfaces from sectors actually derived from the displayed core action;
- evaluates exact Gate-2B inflation as `REVIEW`, not as a validated FToE prediction;
- treats the theta23 executable as a toy sensitivity interface, not empirical DUNE validation;
- gives every candidate a deterministic SHA-256-derived ID;
- forbids the engine from emitting `VERIFIED`.

## Existing-data basis

The seed registry is a compact machine-readable encoding of the current project record:

- `FTOE-REC-v3`: recalibrated FToE displayed action, still incomplete (`L_cross`, `L_suppression`, Planck convention, coefficient-complete field equations, closed observable map unresolved).
- `FUEF-INFL-GATE2B-EXACT`: exact perturbation result with `ns=0.9691054699`, `r=0.00789582082`, `alpha_s=-0.00118052662`, `n_t=-0.00101873333`, and exact-normalized `A=2.8317639512e-11`; exact/numerical gates passed, conventional self-reheating is a conditional kill, external CMB likelihood not executed.
- `FTOE-INFL-P3-BEST`: historical `r≈0.09081` branch retained only as a falsified regression case.
- `FTOE-DARK-MIN-102`: minimal ~102 GeV Higgs-portal branch retained only as a falsified regression case.
- `NU-MSW-LMA-LIMIT`: established empirical/phenomenology interface, not a new FToE derivation.
- `NU-THETA23-47-TOY`: deterministic toy falsifiability interface; disappearance-only model is insufficient for a ToE neutrino validation.
- `FTOE-R2-BOUNCE-AS-WRITTEN`: failed-as-written cosmology regression case.
- `GR-LCDM-NULL-LIMIT`: empirical low-energy envelope, not a UV origin mechanism.

## Gates

Each candidate is checked through:

1. `G0_PROVENANCE`
2. `G1_NO_FALSIFIED_COMPONENT`
3. `G2_CORE_CLOSURE`
4. `G3_DERIVATION_COVERAGE`
5. `G4_INFLATION`
6. `G5_DARK`
7. `G6_NEUTRINO`
8. `G7_UV_CLOSURE`
9. `G8_COSMOLOGY`
10. `G9_EXTERNAL_CERTIFICATION`

`G9` is always `PENDING_INDEPENDENT_CROSS_CHECK` in v0.1.

## Run

```bash
cd candidates/toe-generator-v0.1
python -m unittest -v test_toe_engine.py
python toe_engine.py regressions
python toe_engine.py generate --top 12
python toe_engine.py test
```

Default generation currently produces 48 composites after excluding hard-falsified components. The highest-ranked object is still expected to be `REVIEW`, because the available project evidence does not close all cross-sector derivations or independent likelihood gates.

## Non-negotiable mutation rule

A failed candidate is never repaired in place. A substantive action, field-content, parameter, or observable-map change creates a **new candidate ID**. Historical failure evidence remains preserved.

## v0.2 automation gates

1. replace summary-level Gate-2B data with an executable exact-background/perturbation adapter;
2. add fail-closed external CMB likelihood adapter;
3. attach frozen NuFIT data identity and a real neutrino likelihood path;
4. add symbolic action/equation coefficient-completeness checks;
5. add independent RGE/unification regression machinery;
6. add dark-sector relic/direct-detection evaluation;
7. re-run all candidate enumeration after every material adapter change;
8. preserve every prior candidate and result as immutable evidence.
