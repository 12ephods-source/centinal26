from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from openquest.rules import get_profile, level_one_hit_points


class GateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class GateResult:
    gate: str
    status: GateStatus
    detail: str


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    version: str
    license_id: str
    attribution: str
    publication_status: str

    def validate(self) -> GateResult:
        missing = [name for name, value in asdict(self).items() if not value]
        if missing:
            return GateResult(
                "SOURCE_GATE",
                GateStatus.FAIL,
                f"Missing provenance fields: {', '.join(missing)}",
            )
        if self.publication_status not in {"PUBLISHABLE", "REFERENCE_ONLY", "QUARANTINED"}:
            return GateResult("SOURCE_GATE", GateStatus.FAIL, "Invalid publication status")
        if self.publication_status == "QUARANTINED":
            return GateResult("SOURCE_GATE", GateStatus.UNRESOLVED, "Source is quarantined")
        return GateResult("SOURCE_GATE", GateStatus.PASS, "Source provenance is explicit")


SRD_521 = SourceRecord(
    source_id="srd-5.2.1",
    version="5.2.1",
    license_id="CC-BY-4.0",
    attribution="Dungeons & Dragons System Reference Document 5.2.1 by Wizards of the Coast LLC, licensed under CC BY 4.0.",
    publication_status="PUBLISHABLE",
)

SRD_51 = SourceRecord(
    source_id="srd-5.1",
    version="5.1",
    license_id="CC-BY-4.0",
    attribution="Dungeons & Dragons System Reference Document 5.1 by Wizards of the Coast LLC, licensed under CC BY 4.0.",
    publication_status="PUBLISHABLE",
)


@dataclass
class Character:
    name: str
    level: int = 1
    ruleset: str = "auto"
    import_format: str | None = None
    ability_scores: dict[str, int] = field(default_factory=dict)
    class_name: str | None = None
    species: str | None = None
    background: str | None = None
    proficiencies: list[str] = field(default_factory=list)
    skill_proficiencies: list[str] = field(default_factory=list)
    hit_points: int | None = None
    armor_class: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


SUPPORTED_RULESETS = {"srd-5.2.1", "srd-5.1"}
ABILITIES = ("str", "dex", "con", "int", "wis", "cha")


def modifier(score: int) -> int:
    return (score - 10) // 2


def resolve_ruleset(character: Character, campaign_override: str | None = None) -> GateResult:
    if campaign_override:
        if campaign_override not in SUPPORTED_RULESETS:
            return GateResult("CANON_GATE", GateStatus.FAIL, f"Unknown campaign ruleset {campaign_override}")
        character.ruleset = campaign_override
        return GateResult("CANON_GATE", GateStatus.PASS, f"Campaign override selected {campaign_override}")

    if character.ruleset != "auto":
        if character.ruleset not in SUPPORTED_RULESETS:
            return GateResult("CANON_GATE", GateStatus.FAIL, f"Unknown explicit ruleset {character.ruleset}")
        return GateResult("CANON_GATE", GateStatus.PASS, f"Explicit ruleset {character.ruleset}")

    if character.import_format == "2014":
        character.ruleset = "srd-5.1"
        return GateResult("CANON_GATE", GateStatus.PASS, "Legacy 2014 import resolved to SRD 5.1")
    if character.import_format == "2024":
        character.ruleset = "srd-5.2.1"
        return GateResult("CANON_GATE", GateStatus.PASS, "2024 import resolved to SRD 5.2.1")
    if character.import_format not in {None, "new"}:
        return GateResult("CANON_GATE", GateStatus.UNRESOLVED, "Import format is ambiguous")

    character.ruleset = "srd-5.2.1"
    return GateResult("CANON_GATE", GateStatus.PASS, "New character defaults to SRD 5.2.1")


def validate_character(character: Character, campaign_override: str | None = None) -> list[GateResult]:
    results: list[GateResult] = []
    canon = resolve_ruleset(character, campaign_override)
    results.append(canon)
    if canon.status != GateStatus.PASS:
        return results

    source = SRD_521 if character.ruleset == "srd-5.2.1" else SRD_51
    results.append(source.validate())

    if character.level != 1:
        results.append(GateResult("CHARACTER_GATE", GateStatus.FAIL, "Vertical slice supports level 1 only"))

    missing_abilities = [a for a in ABILITIES if a not in character.ability_scores]
    if missing_abilities:
        results.append(GateResult("CHARACTER_GATE", GateStatus.FAIL, f"Missing abilities: {', '.join(missing_abilities)}"))
    else:
        bad = {k: v for k, v in character.ability_scores.items() if k in ABILITIES and not 1 <= v <= 30}
        if bad:
            results.append(GateResult("CHARACTER_GATE", GateStatus.FAIL, f"Ability scores out of range: {bad}"))

    required = [
        ("class", character.class_name),
        ("species", character.species),
        ("background", character.background),
        ("hit_points", character.hit_points),
        ("armor_class", character.armor_class),
    ]
    missing = [name for name, value in required if value in {None, ""}]
    if missing:
        results.append(GateResult("CHARACTER_GATE", GateStatus.FAIL, f"Missing required selections: {', '.join(missing)}"))

    duplicates = _duplicates(character.proficiencies + character.skill_proficiencies)
    if duplicates:
        results.append(GateResult("VALIDATION_GATE", GateStatus.FAIL, f"Duplicate proficiencies: {', '.join(sorted(duplicates))}"))

    if character.hit_points is not None and character.hit_points <= 0:
        results.append(GateResult("VALIDATION_GATE", GateStatus.FAIL, "Hit points must be positive"))
    if character.armor_class is not None and not 1 <= character.armor_class <= 40:
        results.append(GateResult("VALIDATION_GATE", GateStatus.FAIL, "Armor class outside supported range"))

    _validate_rules_data(character, results)

    if not any(r.gate == "CHARACTER_GATE" and r.status == GateStatus.FAIL for r in results):
        results.append(GateResult("CHARACTER_GATE", GateStatus.PASS, "Required level-1 character fields are complete"))
    if not any(r.gate == "VALIDATION_GATE" and r.status == GateStatus.FAIL for r in results):
        results.append(GateResult("VALIDATION_GATE", GateStatus.PASS, "Deterministic structural validation passed"))
    if not any(r.gate == "RULE_DATA_GATE" and r.status == GateStatus.FAIL for r in results):
        results.append(GateResult("RULE_DATA_GATE", GateStatus.PASS, "Selections match the versioned SRD profile"))

    return results


def _validate_rules_data(character: Character, results: list[GateResult]) -> None:
    profile = get_profile(character.ruleset)

    if character.class_name not in profile.classes:
        results.append(GateResult("RULE_DATA_GATE", GateStatus.FAIL, f"Unsupported class for {profile.ruleset}: {character.class_name}"))
        return
    if character.species not in profile.species:
        results.append(GateResult("RULE_DATA_GATE", GateStatus.FAIL, f"Unsupported species for {profile.ruleset}: {character.species}"))
    if character.background not in profile.backgrounds:
        results.append(GateResult("RULE_DATA_GATE", GateStatus.FAIL, f"Unsupported background for {profile.ruleset}: {character.background}"))

    class_rule = profile.classes[character.class_name]
    skills = set(character.skill_proficiencies)
    if len(character.skill_proficiencies) != class_rule.skill_choices:
        results.append(
            GateResult(
                "RULE_DATA_GATE",
                GateStatus.FAIL,
                f"{class_rule.name} requires {class_rule.skill_choices} class skill choices",
            )
        )
    invalid_skills = skills - class_rule.allowed_skills
    if invalid_skills:
        results.append(
            GateResult(
                "RULE_DATA_GATE",
                GateStatus.FAIL,
                f"Invalid {class_rule.name} class skills: {', '.join(sorted(invalid_skills))}",
            )
        )

    constitution = character.ability_scores.get("con")
    if constitution is not None and character.hit_points is not None:
        expected_hp = level_one_hit_points(class_rule, constitution)
        if character.hit_points != expected_hp:
            results.append(
                GateResult(
                    "RULE_DATA_GATE",
                    GateStatus.FAIL,
                    f"Level-1 {class_rule.name} hit points must be {expected_hp}",
                )
            )


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def export_character(character: Character, results: list[GateResult]) -> str:
    profile = get_profile(character.ruleset)
    payload = {
        "schema": "openquest.character.v1",
        "character": asdict(character),
        "ruleset": character.ruleset,
        "rule_profile": {"ruleset": profile.ruleset, "source_id": profile.source_id},
        "source": asdict(SRD_521 if character.ruleset == "srd-5.2.1" else SRD_51),
        "gates": [
            {"gate": r.gate, "status": r.status.value, "detail": r.detail}
            for r in results
        ],
        "valid": all(r.status == GateStatus.PASS for r in results),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def demo() -> int:
    c = Character(
        name="OpenQuest Demo",
        ability_scores={"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8},
        class_name="Fighter",
        species="Human",
        background="Soldier",
        proficiencies=["light armor", "medium armor", "shields"],
        skill_proficiencies=["athletics", "perception"],
        hit_points=11,
        armor_class=16,
    )
    results = validate_character(c)
    print(export_character(c, results))
    return 0 if all(r.status == GateStatus.PASS for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(demo())
