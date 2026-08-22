from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClassRule:
    name: str
    hit_die: int
    saving_throws: tuple[str, ...]
    skill_choices: int
    allowed_skills: frozenset[str]
    armor: frozenset[str]
    weapons: frozenset[str]


@dataclass(frozen=True)
class RulesProfile:
    ruleset: str
    source_id: str
    classes: dict[str, ClassRule]
    species: frozenset[str]
    backgrounds: frozenset[str]


FIGHTER_SKILLS = frozenset(
    {
        "acrobatics",
        "animal handling",
        "athletics",
        "history",
        "insight",
        "intimidation",
        "perception",
        "persuasion",
        "survival",
    }
)


FIGHTER_521 = ClassRule(
    name="Fighter",
    hit_die=10,
    saving_throws=("str", "con"),
    skill_choices=2,
    allowed_skills=FIGHTER_SKILLS,
    armor=frozenset({"light armor", "medium armor", "heavy armor", "shields"}),
    weapons=frozenset({"simple weapons", "martial weapons"}),
)

FIGHTER_51 = ClassRule(
    name="Fighter",
    hit_die=10,
    saving_throws=("str", "con"),
    skill_choices=2,
    allowed_skills=FIGHTER_SKILLS,
    armor=frozenset({"light armor", "medium armor", "heavy armor", "shields"}),
    weapons=frozenset({"simple weapons", "martial weapons"}),
)


PROFILES: dict[str, RulesProfile] = {
    "srd-5.2.1": RulesProfile(
        ruleset="srd-5.2.1",
        source_id="srd-5.2.1",
        classes={"Fighter": FIGHTER_521},
        species=frozenset({"Human"}),
        backgrounds=frozenset({"Soldier"}),
    ),
    "srd-5.1": RulesProfile(
        ruleset="srd-5.1",
        source_id="srd-5.1",
        classes={"Fighter": FIGHTER_51},
        species=frozenset({"Human"}),
        backgrounds=frozenset({"Soldier"}),
    ),
}


def get_profile(ruleset: str) -> RulesProfile:
    try:
        return PROFILES[ruleset]
    except KeyError as exc:
        raise ValueError(f"Unsupported ruleset: {ruleset}") from exc


def level_one_hit_points(class_rule: ClassRule, constitution_score: int) -> int:
    return class_rule.hit_die + (constitution_score - 10) // 2
