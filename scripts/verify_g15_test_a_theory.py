from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "test_a_theory.py"
HELDOUT = ROOT / "validation" / "test_a_theory" / "heldout_cases.json"


class VerificationFailure(RuntimeError):
    pass


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationFailure(message)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _assert(isinstance(value, dict), f"{path} is not a JSON object")
    return value


def _base_model(model_id: str) -> dict[str, Any]:
    return {
        "predictions": [
            {
                "absolute_tolerance": 0.02,
                "observed": 1.005,
                "predicted": 1.0,
                "prediction_id": "independent-frequency-ratio",
            }
        ],
        "schema": "test-a-theory/model-v1",
        "equations": [
            {
                "right": {"frequency": 1},
                "equation_id": "inverse-period-frequency",
                "left": {"period": -1},
            }
        ],
        "model_id": model_id,
        "symbol_dimensions": {"period": [0, 0, 1], "frequency": [0, 0, -1]},
        "provenance_refs": ["independent-verifier:synthetic-case-v1"],
    }


def _invoke(
    model: dict[str, Any], work: Path, name: str
) -> tuple[subprocess.CompletedProcess[str], Path]:
    input_path = work / f"{name}.json"
    output_dir = work / f"{name}-package"
    input_path.write_text(
        json.dumps(model, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    result = subprocess.run(
        [sys.executable, str(CLI), str(input_path), str(output_dir)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    return result, output_dir


def _verify_package(
    model: dict[str, Any], output_dir: Path, *, expected_verdict: str
) -> dict[str, bytes]:
    _assert(output_dir.is_dir(), f"missing reproducibility package {output_dir}")
    expected_names = {"input.json", "report.json", "manifest.json"}
    actual_names = {path.name for path in output_dir.iterdir() if path.is_file()}
    _assert(
        actual_names == expected_names,
        f"unexpected package files: {sorted(actual_names)}",
    )
    input_bytes = (output_dir / "input.json").read_bytes()
    report_bytes = (output_dir / "report.json").read_bytes()
    manifest_bytes = (output_dir / "manifest.json").read_bytes()
    _assert(
        json.loads(input_bytes.decode("utf-8")) == model,
        "packaged input differs from submitted model",
    )
    report = json.loads(report_bytes.decode("utf-8"))
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    _assert(report.get("schema") == "test-a-theory/report-v1", "wrong report schema")
    _assert(report.get("model_id") == model["model_id"], "report/model identity mismatch")
    _assert(report.get("verdict") == expected_verdict, "unexpected report verdict")
    expected_input_sha = _sha256_bytes(_canonical_json(model).encode("utf-8"))
    _assert(
        report.get("input_sha256") == expected_input_sha,
        "report input hash is not canonical model hash",
    )
    _assert(
        "do not establish scientific truth"
        in str(report.get("epistemic_boundary", "")).lower(),
        "scientific-truth boundary missing",
    )
    _assert(
        manifest.get("schema") == "test-a-theory/reproducibility-manifest-v1",
        "wrong manifest schema",
    )
    files = manifest.get("files")
    _assert(isinstance(files, dict), "manifest files map missing")
    _assert(
        files.get("input.json") == _sha256_bytes(input_bytes),
        "input.json hash mismatch",
    )
    _assert(
        files.get("report.json") == _sha256_bytes(report_bytes),
        "report.json hash mismatch",
    )
    return {
        "input.json": input_bytes,
        "report.json": report_bytes,
        "manifest.json": manifest_bytes,
    }


def verify() -> dict[str, Any]:
    heldout = _read_json(HELDOUT)
    frozen_ids = {
        str(case.get("case_id"))
        for case in heldout.get("cases", [])
        if isinstance(case, dict)
    }
    independent_ids = {
        "independent-pass-v1",
        "independent-dimension-fail-v1",
        "independent-prediction-fail-v1",
        "independent-empty-gates-v1",
    }
    _assert(
        not (frozen_ids & independent_ids),
        "independent cases overlap frozen repository fixtures",
    )

    with tempfile.TemporaryDirectory(prefix="g15-independent-") as tmp:
        work = Path(tmp)
        pass_model = _base_model("independent-pass-v1")
        first, first_dir = _invoke(pass_model, work, "pass-a")
        _assert(
            first.returncode == 0,
            f"passing CLI case returned {first.returncode}: {first.stderr}",
        )
        _assert(
            json.loads(first.stdout).get("verdict") == "PASS_DECLARED_GATES",
            "passing stdout verdict wrong",
        )
        package_a = _verify_package(
            pass_model, first_dir, expected_verdict="PASS_DECLARED_GATES"
        )

        reordered = {
            "model_id": pass_model["model_id"],
            "provenance_refs": pass_model["provenance_refs"],
            "symbol_dimensions": pass_model["symbol_dimensions"],
            "equations": pass_model["equations"],
            "predictions": pass_model["predictions"],
            "schema": pass_model["schema"],
        }
        second, second_dir = _invoke(reordered, work, "pass-b")
        _assert(
            second.returncode == 0,
            f"replay returned {second.returncode}: {second.stderr}",
        )
        package_b = _verify_package(
            reordered, second_dir, expected_verdict="PASS_DECLARED_GATES"
        )
        _assert(
            package_a == package_b,
            "deterministic replay package differs byte-for-byte",
        )

        dimension_fail = _base_model("independent-dimension-fail-v1")
        dimension_fail["equations"][0]["right"] = {"period": 1}
        dim_run, dim_dir = _invoke(dimension_fail, work, "dimension-fail")
        _assert(
            dim_run.returncode == 1,
            f"dimension falsification returned {dim_run.returncode}",
        )
        dim_report = json.loads(
            _verify_package(
                dimension_fail, dim_dir, expected_verdict="FAIL_DECLARED_GATES"
            )["report.json"]
        )
        _assert(
            dim_report["dimensional_checks"][0]["status"] == "FAIL",
            "dimensional mismatch was not exposed",
        )

        prediction_fail = _base_model("independent-prediction-fail-v1")
        prediction_fail["predictions"][0]["observed"] = 1.2
        pred_run, pred_dir = _invoke(prediction_fail, work, "prediction-fail")
        _assert(
            pred_run.returncode == 1,
            f"prediction falsification returned {pred_run.returncode}",
        )
        pred_report = json.loads(
            _verify_package(
                prediction_fail, pred_dir, expected_verdict="FAIL_DECLARED_GATES"
            )["report.json"]
        )
        _assert(
            pred_report["prediction_checks"][0]["status"] == "FAIL",
            "out-of-tolerance prediction was not exposed",
        )

        no_gates = _base_model("independent-empty-gates-v1")
        no_gates["equations"] = []
        no_gates["predictions"] = []
        empty_run, empty_dir = _invoke(no_gates, work, "empty-gates")
        _assert(
            empty_run.returncode == 1,
            "model with no declared gates did not fail closed",
        )
        _verify_package(no_gates, empty_dir, expected_verdict="FAIL_DECLARED_GATES")

        for name, mutate, expected_fragment in (
            (
                "missing-provenance",
                lambda model: model.__setitem__("provenance_refs", []),
                "provenance_refs",
            ),
            (
                "unknown-symbol",
                lambda model: model["equations"][0].__setitem__(
                    "right", {"ghost": 1}
                ),
                "unknown symbol",
            ),
        ):
            invalid = _base_model(f"independent-{name}-v1")
            mutate(invalid)
            invalid_run, invalid_dir = _invoke(invalid, work, name)
            _assert(
                invalid_run.returncode == 2,
                f"{name} did not return CLI error status 2",
            )
            error = json.loads(invalid_run.stdout)
            _assert(
                error.get("status") == "ERROR",
                f"{name} did not emit structured ERROR",
            )
            _assert(
                expected_fragment in str(error.get("error", "")),
                f"{name} error reason missing",
            )
            _assert(
                not invalid_dir.exists(),
                f"{name} emitted a package despite invalid input",
            )

        mutated = _base_model("independent-pass-v1")
        mutated["predictions"][0]["observed"] = 1.006
        changed_run, changed_dir = _invoke(mutated, work, "changed-input")
        _assert(changed_run.returncode == 0, "valid changed-input case failed")
        changed_package = _verify_package(
            mutated, changed_dir, expected_verdict="PASS_DECLARED_GATES"
        )
        _assert(
            changed_package["report.json"] != package_a["report.json"],
            "input mutation did not change report evidence",
        )

    return {
        "schema": "g15-independent-verification/v1",
        "goal_id": "G15",
        "verdict": "VERIFIED",
        "scope": "black-box host verification of the Test-a-Theory MVP public CLI",
        "criteria": {
            "explicit_model_input": "PASS",
            "dimensional_consistency_gate": "PASS",
            "numerical_falsification_gate": "PASS",
            "empty_gate_fail_closed": "PASS",
            "invalid_input_fail_closed": "PASS",
            "reproducibility_package_hash_readback": "PASS",
            "byte_identical_deterministic_replay": "PASS",
            "input_mutation_evidence_sensitivity": "PASS",
            "verifier_owned_unseen_cases": "PASS",
            "scientific_truth_boundary_preserved": "PASS",
        },
        "limits": [
            "verifies software behavior, not scientific truth",
            "verifier-owned cases are synthetic host cases, not empirical evidence",
            "does not validate any particular physical theory or dataset",
            "does not establish deployment or commercial adoption",
        ],
    }


def main() -> int:
    try:
        result = verify()
    except (
        VerificationFailure,
        OSError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        print(
            json.dumps(
                {
                    "schema": "g15-independent-verification/v1",
                    "goal_id": "G15",
                    "verdict": "FAIL",
                    "error": str(exc),
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
