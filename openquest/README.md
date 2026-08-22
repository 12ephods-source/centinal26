# OpenQuest Character Creator + Rules Validator

Status: bounded character-creator vertical slice.

## Canon policy

OpenQuest never silently merges mechanically distinct rules generations.

Resolution order:

1. explicit campaign override
2. explicitly selected ruleset
3. SRD 5.2.1 for new characters
4. SRD 5.1 for unmistakable legacy imports
5. otherwise `CANON_UNRESOLVED`

Supported profiles:

- `srd-5.2.1` — default, corresponding to the revised 2024 D&D 5e rules published through SRD 5.2.1.
- `srd-5.1` — legacy compatibility profile corresponding to the 2014 D&D 5e rules.

## Provenance policy

Every rule record must carry source/version/license/provenance metadata. A build may publish only records classified `PUBLISHABLE`. Reference-only or unknown-provenance material is excluded from distributable bundles.

No copyrighted source text is embedded by this slice. The engine stores compact rule facts and provenance metadata only.

## Construction workflow

`openquest.builder` turns the rules profile into legal construction options before a character exists. The current bounded slice exposes the supported class/species/background choices, requires an exact standard-array assignment, checks class-skill choices, derives level-1 HP and class proficiencies, then sends the constructed character through the independent validator.

This creates two fail-closed layers:

`BUILD_GATE -> SOURCE_GATE -> CANON_GATE -> CHARACTER_GATE -> VALIDATION_GATE -> RULE_DATA_GATE`

The builder currently supports the intentionally narrow Fighter/Human/Soldier level-1 path in both versioned profiles. Unsupported choices fail instead of being guessed or silently mixed across rules generations.

## Current finish line

`versioned source -> generated legal options -> bounded construction -> derived mechanics -> independent validation -> deterministic JSON export -> CI`

Out of scope: combat, spells, feats, equipment simulation, AI DM, world generation, multiplayer, marketplace, adventure generation, and full campaign simulation.

Run:

```bash
python -m openquest.validator
python -m unittest discover -s openquest/tests -v
```
