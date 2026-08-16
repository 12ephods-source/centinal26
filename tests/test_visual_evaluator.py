from centinal26.visual_evaluator import MultimodalEvaluator, scores_from_evidence


def test_hard_gate_failure_overrides_scores():
    evaluator = MultimodalEvaluator()
    evidence = evaluator._normalize({
        "hard_gates": {
            "image_integrity": True,
            "locked_foreground_identity": True,
            "no_unrequested_entities": True,
            "target_constraint": False,
        },
        "scores": {"preservation": .99, "target_gain": .99, "collateral_drift": .01},
        "confidence": .9,
    })
    assert evidence["status"] == "HARD_GATE_FAIL"
    assert evidence["scores"] == {
        "preservation": 0.0,
        "target_gain": 0.0,
        "collateral_drift": 1.0,
    }


def test_verified_scores_are_bounded():
    evaluator = MultimodalEvaluator()
    evidence = evaluator._normalize({
        "hard_gates": {
            "image_integrity": True,
            "locked_foreground_identity": True,
            "no_unrequested_entities": True,
            "target_constraint": True,
        },
        "scores": {"preservation": 1.4, "target_gain": .2, "collateral_drift": -.1},
        "confidence": 2,
    })
    assert evidence["status"] == "VERIFIED"
    assert evidence["scores"] == {
        "preservation": 1.0,
        "target_gain": .2,
        "collateral_drift": 0.0,
    }
    scores = scores_from_evidence(evidence)
    assert scores.preservation == 1.0
    assert evidence["confidence"] == 1.0
