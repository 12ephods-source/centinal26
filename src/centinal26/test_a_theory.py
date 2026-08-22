from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

Dimension = tuple[int, ...]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _require_refs(refs: list[str]) -> None:
    if not refs or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        raise ValueError("model requires non-empty provenance_refs")


def _dimension_of_monomial(
    monomial: dict[str, int], symbol_dimensions: dict[str, Dimension]
) -> Dimension:
    if not monomial:
        raise ValueError("monomial must contain at least one symbol")
    width = len(next(iter(symbol_dimensions.values())))
    result = [0] * width
    for symbol, power in monomial.items():
        if symbol not in symbol_dimensions:
            raise ValueError(f"unknown symbol in monomial: {symbol}")
        if not isinstance(power, int) or isinstance(power, bool):
            raise TypeError("monomial powers must be integers")
        for index, exponent in enumerate(symbol_dimensions[symbol]):
            result[index] += exponent * power
    return tuple(result)


@dataclass(frozen=True)
class TheoryReport:
    model_id: str
    input_sha256: str
    dimensional_checks: tuple[dict[str, Any], ...]
    prediction_checks: tuple[dict[str, Any], ...]
    verdict: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "test-a-theory/report-v1",
            "model_id": self.model_id,
            "input_sha256": self.input_sha256,
            "dimensional_checks": list(self.dimensional_checks),
            "prediction_checks": list(self.prediction_checks),
            "verdict": self.verdict,
            "epistemic_boundary": (
                "Software checks establish only the declared dimensional and numerical "
                "test outcomes; they do not establish scientific truth."
            ),
        }


def evaluate_model(model: dict[str, Any]) -> TheoryReport:
    """Evaluate one explicit model using bounded deterministic consistency/falsification gates."""

    if model.get("schema") != "test-a-theory/model-v1":
        raise ValueError("unsupported model schema")
    model_id = model.get("model_id")
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("model_id must be non-empty")
    refs = model.get("provenance_refs")
    if not isinstance(refs, list):
        raise TypeError("provenance_refs must be a list")
    _require_refs(refs)

    raw_dimensions = model.get("symbol_dimensions")
    if not isinstance(raw_dimensions, dict) or not raw_dimensions:
        raise ValueError("symbol_dimensions must be a non-empty object")
    symbol_dimensions: dict[str, Dimension] = {}
    width: int | None = None
    for symbol, raw_dimension in raw_dimensions.items():
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("dimension symbol names must be non-empty")
        if not isinstance(raw_dimension, list) or not raw_dimension:
            raise ValueError(f"dimension vector for {symbol} must be a non-empty list")
        if any(not isinstance(value, int) or isinstance(value, bool) for value in raw_dimension):
            raise TypeError("dimension vector entries must be integers")
        dimension = tuple(raw_dimension)
        if width is None:
            width = len(dimension)
        elif len(dimension) != width:
            raise ValueError("all dimension vectors must have equal length")
        symbol_dimensions[symbol] = dimension

    dimensional_checks: list[dict[str, Any]] = []
    equations = model.get("equations", [])
    if not isinstance(equations, list):
        raise TypeError("equations must be a list")
    for index, equation in enumerate(equations):
        if not isinstance(equation, dict):
            raise TypeError("equation entries must be objects")
        equation_id = equation.get("equation_id", f"equation-{index}")
        left = equation.get("left")
        right = equation.get("right")
        if not isinstance(left, dict) or not isinstance(right, dict):
            raise TypeError("equation left/right must be monomial objects")
        left_dimension = _dimension_of_monomial(left, symbol_dimensions)
        right_dimension = _dimension_of_monomial(right, symbol_dimensions)
        passed = left_dimension == right_dimension
        dimensional_checks.append(
            {
                "equation_id": str(equation_id),
                "left_dimension": list(left_dimension),
                "right_dimension": list(right_dimension),
                "status": "PASS" if passed else "FAIL",
            }
        )

    prediction_checks: list[dict[str, Any]] = []
    predictions = model.get("predictions", [])
    if not isinstance(predictions, list):
        raise TypeError("predictions must be a list")
    for index, prediction in enumerate(predictions):
        if not isinstance(prediction, dict):
            raise TypeError("prediction entries must be objects")
        prediction_id = prediction.get("prediction_id", f"prediction-{index}")
        predicted = prediction.get("predicted")
        observed = prediction.get("observed")
        tolerance = prediction.get("absolute_tolerance")
        values = (predicted, observed, tolerance)
        if any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in values):
            raise TypeError("prediction values and tolerance must be numeric")
        if any(not math.isfinite(float(value)) for value in values):
            raise ValueError("prediction values and tolerance must be finite")
        if tolerance < 0:
            raise ValueError("absolute_tolerance cannot be negative")
        residual = abs(float(predicted) - float(observed))
        passed = residual <= float(tolerance)
        prediction_checks.append(
            {
                "prediction_id": str(prediction_id),
                "predicted": predicted,
                "observed": observed,
                "absolute_tolerance": tolerance,
                "absolute_residual": residual,
                "status": "PASS" if passed else "FAIL",
            }
        )

    all_checks = dimensional_checks + prediction_checks
    verdict = "PASS_DECLARED_GATES" if all_checks and all(
        check["status"] == "PASS" for check in all_checks
    ) else "FAIL_DECLARED_GATES"
    input_sha256 = _sha256_text(_canonical_json(model))
    return TheoryReport(
        model_id=model_id,
        input_sha256=input_sha256,
        dimensional_checks=tuple(dimensional_checks),
        prediction_checks=tuple(prediction_checks),
        verdict=verdict,
    )


def write_reproducibility_package(model: dict[str, Any], output_dir: Path) -> TheoryReport:
    """Write canonical input/report plus a SHA-256 manifest for reproducible readback."""

    report = evaluate_model(model)
    output_dir.mkdir(parents=True, exist_ok=True)
    input_text = json.dumps(model, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    report_text = json.dumps(report.as_dict(), sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    (output_dir / "input.json").write_text(input_text, encoding="utf-8")
    (output_dir / "report.json").write_text(report_text, encoding="utf-8")
    manifest = {
        "schema": "test-a-theory/reproducibility-manifest-v1",
        "files": {
            "input.json": hashlib.sha256(input_text.encode("utf-8")).hexdigest(),
            "report.json": hashlib.sha256(report_text.encode("utf-8")).hexdigest(),
        },
    }
    manifest_text = json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    (output_dir / "manifest.json").write_text(manifest_text, encoding="utf-8")
    return report
