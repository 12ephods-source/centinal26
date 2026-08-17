"""Heavy-threshold matching gate for the repaired FToE SO(10)->422 branch.

The script consumes a frozen heavy-spectrum JSON rather than fitting masses to
force unification. Each entry supplies the heavy mass and its one-loop beta
contribution in the matching basis. The gate computes differential threshold
corrections and reports whether a pre-declared spectrum closes a supplied
inverse-coupling residual.

No spectrum is inferred here. Missing masses or beta coefficients are a
scientific NOT_TESTED condition, not a value to be optimized post hoc.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

PI = math.pi


@dataclass
class Multiplet:
    name: str
    mass_GeV: float
    beta: dict[str, float]
    source: str = ""


def load_spectrum(path: Path) -> list[Multiplet]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("multiplets", raw if isinstance(raw, list) else [])
    if not rows:
        raise ValueError("spectrum contains no multiplets")
    out = []
    for row in rows:
        name = str(row["name"])
        mass = float(row["mass_GeV"])
        beta = {str(k): float(v) for k, v in row["beta"].items()}
        if mass <= 0:
            raise ValueError(f"non-positive mass for {name}")
        if len(beta) < 2:
            raise ValueError(f"insufficient beta components for {name}")
        out.append(
            Multiplet(
                name=name,
                mass_GeV=mass,
                beta=beta,
                source=str(row.get("source", "")),
            )
        )
    return out


def threshold_corrections(
    spectrum: list[Multiplet],
    matching_scale: float,
) -> dict[str, float]:
    if matching_scale <= 0:
        raise ValueError("matching scale must be positive")
    groups = sorted({group for multiplet in spectrum for group in multiplet.beta})
    delta = {group: 0.0 for group in groups}
    for multiplet in spectrum:
        log_ratio = math.log(multiplet.mass_GeV / matching_scale)
        for group in groups:
            delta[group] += -(
                multiplet.beta.get(group, 0.0) / (2.0 * PI)
            ) * log_ratio
    return delta


def corrected_inverse_couplings(
    raw_inverse: dict[str, float],
    delta: dict[str, float],
    finite: dict[str, float] | None = None,
) -> dict[str, float]:
    finite = finite or {}
    groups = sorted(set(raw_inverse) | set(delta) | set(finite))
    missing = [group for group in groups if group not in raw_inverse]
    if missing:
        raise ValueError(f"raw inverse couplings missing groups: {missing}")
    return {
        group: raw_inverse[group] + delta.get(group, 0.0) + finite.get(group, 0.0)
        for group in groups
    }


def spread(values: dict[str, float]) -> float:
    if len(values) < 2:
        raise ValueError("need at least two couplings")
    return max(values.values()) - min(values.values())


def calculate(
    spectrum_path: Path,
    matching_scale: float,
    raw_inverse: dict[str, float],
    finite: dict[str, float],
    tolerance: float,
) -> dict:
    spectrum = load_spectrum(spectrum_path)
    delta = threshold_corrections(spectrum, matching_scale)
    corrected = corrected_inverse_couplings(raw_inverse, delta, finite)
    before = spread(raw_inverse)
    after = spread(corrected)
    gate = "PASS" if after <= tolerance else "FAIL"
    return {
        "schema": "FTOE-SO10-HEAVY-THRESHOLD-GATE-v0.1",
        "spectrum_file": str(spectrum_path),
        "matching_scale_GeV": matching_scale,
        "multiplet_count": len(spectrum),
        "raw_inverse_couplings": raw_inverse,
        "logarithmic_threshold_corrections": delta,
        "finite_matching_constants": finite,
        "corrected_inverse_couplings": corrected,
        "spread_before": before,
        "spread_after": after,
        "tolerance": tolerance,
        "gate": gate,
        "scientific_status": "REVIEW" if gate == "PASS" else "FAIL",
        "notes": [
            "PASS means the supplied frozen spectrum closes the requested numerical matching tolerance; it does not prove the masses are derived from the SO(10) potential.",
            "The workflow must never optimize spectrum masses after observing this residual.",
            "A full scientific PASS additionally requires derived masses, operator closure, perturbativity, vacuum stability, and proton-decay consistency.",
        ],
    }


def parse_map(text: str) -> dict[str, float]:
    raw = json.loads(text)
    if not isinstance(raw, dict):
        raise TypeError("expected JSON object")
    return {str(k): float(v) for k, v in raw.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spectrum", type=Path, required=True)
    parser.add_argument("--scale", type=float, required=True)
    parser.add_argument(
        "--raw-inverse",
        required=True,
        help='JSON, e.g. {"4":31.1,"L":31.2,"R":31.0}',
    )
    parser.add_argument(
        "--finite",
        default="{}",
        help="optional finite matching constants as JSON",
    )
    parser.add_argument("--tolerance", type=float, default=1e-3)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = calculate(
        args.spectrum,
        args.scale,
        parse_map(args.raw_inverse),
        parse_map(args.finite),
        args.tolerance,
    )
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
