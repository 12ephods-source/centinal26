from centinal26.agents.candidate_toe_generator import generate_candidates, self_test


def test_self_test_passes():
    result = self_test()
    assert result["status"] == "PASS"


def test_generation_is_deterministic():
    a = generate_candidates("test objective", count=6, seed=123, preference="conservative")
    b = generate_candidates("test objective", count=6, seed=123, preference="conservative")
    assert a == b


def test_generator_never_self_promotes():
    candidates = generate_candidates("test objective", count=20, seed=1, preference="novel")
    assert candidates
    assert {x["status"] for x in candidates} == {"PROPOSED"}


def test_bridge_compatibility_is_enforced():
    candidates = generate_candidates("test objective", count=50, seed=1, preference="id")
    for item in candidates:
        c = item["components"]
        if c["bridge"] == "HIGGS_PORTAL":
            assert c["hidden"] == "Z2_SCALAR"
        if c["bridge"] == "KINETIC_MIXING":
            assert c["hidden"] == "DARK_U1"


def test_every_candidate_has_falsification_path():
    candidates = generate_candidates("test objective", count=50, seed=2, preference="simple")
    assert all(item["falsifiers"] for item in candidates)
    assert all(item["required_next_checks"] for item in candidates)
