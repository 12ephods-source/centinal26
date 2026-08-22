import json
from pathlib import Path

import pytest

from centinal26.test_a_theory import evaluate_model, write_reproducibility_package


def valid_model() -> dict:
    return {
        "schema": "test-a-theory/model-v1",
        "model_id": "fixture-valid",
        "provenance_refs": ["fixture:valid"],
        "symbol_dimensions": {
            "mass": [1, 0, 0],
            "velocity": [0, 1, -1],
            "energy": [1, 2, -2],
        },
        "equations": [
            {
                "equation_id": "energy-scale",
                "left": {"energy": 1},
                "right": {"mass": 1, "velocity": 2},
            }
        ],
        "predictions": [
            {
                "prediction_id": "toy-observable",
                "predicted": 10.0,
                "observed": 10.2,
                "absolute_tolerance": 0.25,
            }
        ],
    }


def test_valid_declared_gates_pass() -> None:
    report = evaluate_model(valid_model())
    assert report.verdict == "PASS_DECLARED_GATES"
    assert report.dimensional_checks[0]["status"] == "PASS"
    assert report.prediction_checks[0]["status"] == "PASS"


def test_dimensional_mismatch_fails() -> None:
    model = valid_model()
    model["equations"][0]["right"] = {"mass": 1, "velocity": 1}
    report = evaluate_model(model)
    assert report.verdict == "FAIL_DECLARED_GATES"
    assert report.dimensional_checks[0]["status"] == "FAIL"


def test_prediction_outside_preregistered_tolerance_fails() -> None:
    model = valid_model()
    model["predictions"][0]["observed"] = 10.3
    model["predictions"][0]["absolute_tolerance"] = 0.1
    report = evaluate_model(model)
    assert report.verdict == "FAIL_DECLARED_GATES"
    assert report.prediction_checks[0]["status"] == "FAIL"


def test_unknown_symbol_fails_closed() -> None:
    model = valid_model()
    model["equations"][0]["right"] = {"unknown": 1}
    with pytest.raises(ValueError, match="unknown symbol"):
        evaluate_model(model)


def test_missing_provenance_fails_closed() -> None:
    model = valid_model()
    model["provenance_refs"] = []
    with pytest.raises(ValueError, match="provenance_refs"):
        evaluate_model(model)


def test_non_finite_prediction_fails_closed() -> None:
    model = valid_model()
    model["predictions"][0]["predicted"] = float("inf")
    with pytest.raises(ValueError, match="must be finite"):
        evaluate_model(model)


def test_reproducibility_package_hashes_read_back(tmp_path: Path) -> None:
    report = write_reproducibility_package(valid_model(), tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert report.verdict == "PASS_DECLARED_GATES"
    assert set(manifest["files"]) == {"input.json", "report.json"}
    assert len(manifest["files"]["input.json"]) == 64
    assert len(manifest["files"]["report.json"]) == 64
