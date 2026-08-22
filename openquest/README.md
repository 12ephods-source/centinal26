# OpenQuest Character Creator + Rules Validator

Status: vertical-slice implementation.

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

## Vertical-slice finish line

`source gate -> canon gate -> level-1 character model -> deterministic validator -> JSON export -> tests`

Out of scope for this slice: combat, AI DM, world generation, multiplayer, marketplace, adventure generation, and full campaign simulation.

Run:

```bash
python -m openquest.validator
python -m unittest discover -s openquest/tests -v
```
