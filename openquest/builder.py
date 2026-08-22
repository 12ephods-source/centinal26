from __future__ import annotations

from dataclasses import dataclass

from openquest.rules import get_profile, level_one_hit_points
from openquest.validator import Character, GateResult, GateStatus, validate_character


STANDARD_ARRAY = (15, 14, 13, 12, 10, 8)
ABILITIES = ("str", "dex", "con", "int", "wis", "cha")


@dataclass(frozen=True)
class BuildOptions:
    ruleset: str
    classes: tuple[str, ...]
    species: tuple[str, ...]
    backgrounds: tuple[str, ...]
    standard_array: tuple[int, ...]


@dataclass(frozen=True)
class BuildResult:
    character: Character | None
    gates: tuple[GateResult, ...]

    @property
    def valid(self) -> bool:
        return self.character is not None and all(g.status == GateStatus.PASS for g in self.gates)


def list_options(ruleset: str = "srd-5.2.1") -> BuildOptions:
    profile = get_profile(ruleset)
    return BuildOptions(
        ruleset=profile.ruleset,
        classes=tuple(sorted(profile.classes)),
        species=tuple(sorted(profile.species)),
        backgrounds=tuple(sorted(profile.backgrounds)),
        standard_array=STANDARD_ARRAY,
    )


def build_level_one_character(
    *,
    name: str,
    ability_scores: dict[str, int],
    class_name: str,
    species: str,
    background: str,
    skill_proficiencies: list[str],
    ruleset: str = "srd-5.2.1",
    armor_class: int = 10,
) -> BuildResult:
    try:
        profile = get_profile(ruleset)
    except ValueError as exc:
        return BuildResult(None, (GateResult("BUILD_GATE", GateStatus.FAIL, str(exc)),))

    failures: list[GateResult] = []
    if not name.strip():
        failures.append(GateResult("BUILD_GATE", GateStatus.FAIL, "Character name is required"))
    if set(ability_scores) != set(ABILITIES):
        failures.append(
            GateResult("BUILD_GATE", GateStatus.FAIL, "Exactly six named ability scores are required")
        )
    if sorted(ability_scores.values(), reverse=True) != list(STANDARD_ARRAY):
        failures.append(
            GateResult("BUILD_GATE", GateStatus.FAIL, "Ability scores must be an assignment of the standard array")
        )
    if class_name not in profile.classes:
        failures.append(
            GateResult("BUILD_GATE", GateStatus.FAIL, f"Unsupported class for {ruleset}: {class_name}")
        )
    if species not in profile.species:
        failures.append(
            GateResult("BUILD_GATE", GateStatus.FAIL, f"Unsupported species for {ruleset}: {species}")
        )
    if background not in profile.backgrounds:
        failures.append(
            GateResult("BUILD_GATE", GateStatus.FAIL, f"Unsupported background for {ruleset}: {background}")
        )
    if failures:
        return BuildResult(None, tuple(failures))

    class_rule = profile.classes[class_name]
    skills = [skill.lower() for skill in skill_proficiencies]
    if len(skills) != class_rule.skill_choices or len(set(skills)) != len(skills):
        return BuildResult(
            None,
            (
                GateResult(
                    "BUILD_GATE",
                    GateStatus.FAIL,
                    f"{class_name} requires {class_rule.skill_choices} distinct class skills",
                ),
            ),
        )
    invalid_skills = set(skills) - class_rule.allowed_skills
    if invalid_skills:
        return BuildResult(
            None,
            (
                GateResult(
                    "BUILD_GATE",
                    GateStatus.FAIL,
                    f"Illegal {class_name} class skills: {', '.join(sorted(invalid_skills))}",
                ),
            ),
        )

    character = Character(
        name=name.strip(),
        level=1,
        ruleset=ruleset,
        ability_scores=dict(ability_scores),
        class_name=class_name,
        species=species,
        background=background,
        proficiencies=sorted(class_rule.armor | class_rule.weapons),
        skill_proficiencies=skills,
        hit_points=level_one_hit_points(class_rule, ability_scores["con"]),
        armor_class=armor_class,
        metadata={"construction": "openquest.builder.v1", "ability_method": "standard-array"},
    )
    gates = validate_character(character)
    return BuildResult(character, tuple(gates))
