import pytest

from centinal26.creative_canon import CanonBranch, CanonFact, CreativeCanon


def branch(branch_id: str, parent: str | None = None) -> CanonBranch:
    return CanonBranch(branch_id, parent, (f"fixture:branch:{branch_id}",))


def fact(
    fact_id: str,
    branch_id: str,
    entity_id: str,
    attribute: str,
    value: object,
    supersedes: str | None = None,
) -> CanonFact:
    return CanonFact(
        fact_id=fact_id,
        branch_id=branch_id,
        entity_id=entity_id,
        attribute=attribute,
        value=value,
        provenance_refs=(f"fixture:fact:{fact_id}",),
        supersedes_fact_id=supersedes,
    )


def test_root_fact_resolves() -> None:
    canon = CreativeCanon()
    canon.add_branch(branch("main"))
    canon.add_fact(fact("f1", "main", "aldrick", "hair", "silver"))
    view = canon.view("main")
    assert view.resolved == {"aldrick": {"hair": "silver"}}
    assert view.contradictions == {}


def test_branch_inherits_parent_canon() -> None:
    canon = CreativeCanon()
    canon.add_branch(branch("main"))
    canon.add_branch(branch("variant", "main"))
    canon.add_fact(fact("f1", "main", "hero", "species", "human"))
    assert canon.view("variant").resolved["hero"]["species"] == "human"


def test_provenance_preserving_edit_supersedes_parent_fact() -> None:
    canon = CreativeCanon()
    canon.add_branch(branch("main"))
    canon.add_branch(branch("variant", "main"))
    canon.add_fact(fact("f1", "main", "hero", "weapon", "sword"))
    canon.add_fact(fact("f2", "variant", "hero", "weapon", "bow", supersedes="f1"))
    main = canon.view("main")
    variant = canon.view("variant")
    assert main.resolved["hero"]["weapon"] == "sword"
    assert variant.resolved["hero"]["weapon"] == "bow"
    assert canon.facts()[0].value == "sword"


def test_unresolved_competing_values_are_reported_as_contradiction() -> None:
    canon = CreativeCanon()
    canon.add_branch(branch("main"))
    canon.add_fact(fact("f1", "main", "hero", "age", 18))
    canon.add_fact(fact("f2", "main", "hero", "age", 19))
    view = canon.view("main")
    assert "hero.age" in view.contradictions
    assert "age" not in view.resolved.get("hero", {})


def test_identical_semantic_values_do_not_create_false_contradiction() -> None:
    canon = CreativeCanon()
    canon.add_branch(branch("main"))
    canon.add_fact(fact("f1", "main", "hero", "allies", ["a", "b"]))
    canon.add_fact(fact("f2", "main", "hero", "allies", ["a", "b"]))
    view = canon.view("main")
    assert view.contradictions == {}
    assert view.resolved["hero"]["allies"] == ["a", "b"]


def test_conflicting_stable_fact_identity_fails_closed() -> None:
    canon = CreativeCanon()
    canon.add_branch(branch("main"))
    canon.add_fact(fact("same", "main", "hero", "age", 18))
    with pytest.raises(ValueError, match="conflicting fact identity"):
        canon.add_fact(fact("same", "main", "hero", "age", 19))


def test_unknown_parent_branch_fails_closed() -> None:
    canon = CreativeCanon()
    with pytest.raises(ValueError, match="unknown parent branch"):
        canon.add_branch(branch("variant", "missing"))


def test_supersession_must_preserve_fact_key() -> None:
    canon = CreativeCanon()
    canon.add_branch(branch("main"))
    canon.add_fact(fact("f1", "main", "hero", "age", 18))
    with pytest.raises(ValueError, match="preserve entity and attribute"):
        canon.add_fact(fact("f2", "main", "hero", "hair", "silver", supersedes="f1"))


def test_cannot_supersede_sibling_branch_fact() -> None:
    canon = CreativeCanon()
    canon.add_branch(branch("main"))
    canon.add_branch(branch("a", "main"))
    canon.add_branch(branch("b", "main"))
    canon.add_fact(fact("f1", "a", "hero", "age", 18))
    with pytest.raises(ValueError, match="outside the branch lineage"):
        canon.add_fact(fact("f2", "b", "hero", "age", 19, supersedes="f1"))


def test_missing_provenance_fails_closed() -> None:
    with pytest.raises(ValueError, match="provenance_refs"):
        CanonFact("f1", "main", "hero", "age", 18, ())
