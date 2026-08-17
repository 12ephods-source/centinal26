#!/usr/bin/env python3
"""Heavy-threshold matching gate for the repaired FToE SO(10)->422 branch.

The script consumes a frozen heavy-spectrum JSON rather than fitting masses to
force unification.  Each entry supplies the heavy mass and its one-loop beta
contribution in the matching basis.  The gate computes differential threshold
corrections and reports whether a pre-declared spectrum closes a supplied
inverse-coupling residual.

No spectrum is inferred here.  Missing masses or beta coefficients are a
scientific NOT_TESTED condition, not a value to be optimized post hoc.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List

PI = math.pi


@dataclass
class Multiplet:
    name: str
    mass_GeV: float
    beta: Dict[str, float]
    source: str = ""


def load_spectrum(path: Path) -> List[Multiplet]:
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
        out.append(Multiplet(name=name, mass_GeV=mass, beta=beta, source=str(row.get("source", ""))))
    return out


def threshold_corrections(spectrum: List[Multiplet], matching_scale: float) -> Dict[str, float]:
    if matching_scale <= 0:
        raise ValueError("matching scale must be positive")
    groups = sorted({g for m in spectrum for g in m.beta})
    delta = {g: 0.0 for g in groups}
    for m in spectrum:
        log_ratio = math.log(m.mass_GeV/matching_scale)
        for g in groups:
            # Standard one-loop logarithmic heavy threshold convention used by
            # this gate.  Finite non-logarithmic matching constants, when
            # required by a chosen convention, must be supplied separately.
            delta[g] += -(m.beta.get(g, 0.0)/(2.0*PI))*log_ratio
    return delta


def corrected_inverse_couplings(raw_inverse: Dict[str, float], delta: Dict[str, float], finite: Dict[str, float] | None = None) -> Dict[str, float]:
    finite = finite or {}
    groups = sorted(set(raw_inverse) | set(delta) | set(finite))
    missing = [g for g in groups if g not in raw_inverse]
    if missing:
        raise ValueError(f"raw inverse couplings missing groups: {missing}")
    return {g: raw_inverse[g] + delta.get(g, 0.0) + finite.get(g, 0.0) for g in groups}


def spread(values: Dict[str, float]) -> float:
    if len(values) < 2:
        raise ValueError("need at least two couplings")
    return max(values.values()) - min(values.values())


def calculate(spectrum_path: Path, matching_scale: float, raw_inverse: Dict[str, float], finite: Dict[str, float], tolerance: float) -> Dict:
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
            "A full scientific PASS additionally requires vacuum stability, derived masses, perturbativity, operator closure and proton-decay consistency.",
        ],
    }


def parse_map(text: str) -> Dict[str, float]:
    raw = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError("expected JSON object")
    return {str(k): float(v) for k, v in raw.items()}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--spectrum", type=Path, required=True)
    p.add_argument("--scale", type=float, required=True)
    p.add_argument("--raw-inverse", required=True, help='JSON, e.g. {"4":31.1,"L":31.2,"R":31.0}')
    p.add_argument("--finite", default="{}", help="optional finite matching constants as JSON")
    p.add_argument("--tolerance", type=float, default=1e-3)
    p.add_argument("--json", type=Path)
    args = p.parse_args()
    result = calculate(args.spectrum, args.scale, parse_map(args.raw_inverse), parse_map(args.finite), args.tolerance)
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
