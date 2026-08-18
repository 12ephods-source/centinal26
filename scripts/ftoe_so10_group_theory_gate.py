"""Independently derive gauge-only G422 one- and two-loop beta coefficients.

This gate starts from a frozen representation registry and the generic
semi-simple gauge-theory formulas used in arXiv:1911.11411, Eqs. (2)-(5).
It does not import the coefficient matrices used by the RGE solver.

Conventions:
  a_i = -11/3 C2(G_i) + 4/3 kappa_F sum S2(F_i)
        + 1/3 kappa_S sum S2(S_i)
  b_ij = -34/3 C2(G_i)^2 delta_ij
         + sum_F kappa_F [4 C2(F_j) + 20/3 C2(G_i) delta_ij] S2(F_i)
         + sum_S kappa_S [4 C2(S_j) + 2/3 C2(G_i) delta_ij] S2(S_i)

For a product representation, S2(R_i) includes the dimensions of all spectator
representations. kappa_F=1/2 for Weyl fermions and kappa_S=1 for complex
scalars.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "physics" / "ftoe" / "g422_spectrum_registry.json"
GROUPS = ("SU4C", "SU2L", "SU2R")

REP_DATA = {
    "SU4C": {
        "1": (1, Fraction(0), Fraction(0)),
        "4": (4, Fraction(15, 8), Fraction(1, 2)),
        "4bar": (4, Fraction(15, 8), Fraction(1, 2)),
        "10": (10, Fraction(9, 2), Fraction(3)),
        "10bar": (10, Fraction(9, 2), Fraction(3)),
        "15": (15, Fraction(4), Fraction(4)),
    },
    "SU2L": {
        "1": (1, Fraction(0), Fraction(0)),
        "2": (2, Fraction(3, 4), Fraction(1, 2)),
        "3": (3, Fraction(2), Fraction(2)),
    },
    "SU2R": {
        "1": (1, Fraction(0), Fraction(0)),
        "2": (2, Fraction(3, 4), Fraction(1, 2)),
        "3": (3, Fraction(2), Fraction(2)),
    },
}

C2_G = {
    "SU4C": Fraction(4),
    "SU2L": Fraction(2),
    "SU2R": Fraction(2),
}


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rep_tuple(field: dict) -> tuple[str, str, str]:
    reps = tuple(field["g422"])
    if len(reps) != 3:
        raise ValueError(f"{field['name']}: expected three G422 factors")
    return reps  # type: ignore[return-value]


def spectator_dimension(field: dict, factor_index: int) -> int:
    reps = rep_tuple(field)
    value = int(field.get("multiplicity", 1))
    for idx, group in enumerate(GROUPS):
        if idx == factor_index:
            continue
        value *= REP_DATA[group][reps[idx]][0]
    return value


def dynkin_with_spectators(field: dict, factor_index: int) -> Fraction:
    reps = rep_tuple(field)
    group = GROUPS[factor_index]
    dynkin = REP_DATA[group][reps[factor_index]][2]
    return dynkin * spectator_dimension(field, factor_index)


def casimir(field: dict, factor_index: int) -> Fraction:
    reps = rep_tuple(field)
    group = GROUPS[factor_index]
    return REP_DATA[group][reps[factor_index]][1]


def kappa(field: dict) -> Fraction:
    kind = field["kind"]
    if kind == "weyl_fermion":
        return Fraction(1, 2)
    if kind == "dirac_fermion":
        return Fraction(1)
    if kind == "complex_scalar":
        return Fraction(1)
    if kind == "real_scalar":
        return Fraction(1, 2)
    raise ValueError(f"unsupported field kind: {kind}")


def one_loop(fields: Sequence[dict]) -> tuple[Fraction, Fraction, Fraction]:
    out: list[Fraction] = []
    for i, group in enumerate(GROUPS):
        value = -Fraction(11, 3) * C2_G[group]
        for field in fields:
            s2 = dynkin_with_spectators(field, i)
            if field["kind"] in ("weyl_fermion", "dirac_fermion"):
                value += Fraction(4, 3) * kappa(field) * s2
            else:
                value += Fraction(1, 3) * kappa(field) * s2
        out.append(value)
    return tuple(out)  # type: ignore[return-value]


def two_loop(fields: Sequence[dict]) -> tuple[tuple[Fraction, ...], ...]:
    rows: list[tuple[Fraction, ...]] = []
    for i, group_i in enumerate(GROUPS):
        row: list[Fraction] = []
        for j, _group_j in enumerate(GROUPS):
            delta = Fraction(1 if i == j else 0)
            value = -Fraction(34, 3) * C2_G[group_i] * C2_G[group_i] * delta
            for field in fields:
                s2_i = dynkin_with_spectators(field, i)
                c2_j = casimir(field, j)
                kap = kappa(field)
                if field["kind"] in ("weyl_fermion", "dirac_fermion"):
                    bracket = 4 * c2_j + Fraction(20, 3) * C2_G[group_i] * delta
                else:
                    bracket = 4 * c2_j + Fraction(2, 3) * C2_G[group_i] * delta
                value += kap * bracket * s2_i
            row.append(value)
        rows.append(tuple(row))
    return tuple(rows)


def parse_fraction(text: str) -> Fraction:
    return Fraction(text)


def expected(registry: dict):
    expected_values = registry["expected_gauge_only_coefficients"]
    one = tuple(parse_fraction(x) for x in expected_values["one_loop"])
    two = tuple(tuple(parse_fraction(x) for x in row) for row in expected_values["two_loop_2020"])
    return one, two


def fmt(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def scalar_dynkin_totals(fields: Sequence[dict]) -> tuple[Fraction, Fraction, Fraction]:
    scalars = [field for field in fields if "scalar" in field["kind"]]
    return tuple(
        sum((kappa(field) * dynkin_with_spectators(field, i) for field in scalars), Fraction(0))
        for i in range(3)
    )  # type: ignore[return-value]


def fermion_dynkin_totals(fields: Sequence[dict]) -> tuple[Fraction, Fraction, Fraction]:
    fermions = [field for field in fields if "fermion" in field["kind"]]
    return tuple(
        sum((kappa(field) * dynkin_with_spectators(field, i) for field in fermions), Fraction(0))
        for i in range(3)
    )  # type: ignore[return-value]


def calculate(registry_path: Path = DEFAULT_REGISTRY) -> dict:
    registry = load_registry(registry_path)
    fields = registry["fields"]
    derived_one = one_loop(fields)
    derived_two = two_loop(fields)
    expected_one, expected_two = expected(registry)
    gates = {
        "one_loop_exact_match": "PASS" if derived_one == expected_one else "FAIL",
        "two_loop_exact_match_2020": "PASS" if derived_two == expected_two else "FAIL",
        "b_L4_is_525_over_2": "PASS" if derived_two[1][0] == Fraction(525, 2) else "FAIL",
        "later_525_over_3_reproduced": "PASS" if derived_two[1][0] == Fraction(525, 3) else "FAIL_EXPECTED",
    }
    return {
        "schema": "FTOE-G422-GROUP-THEORY-GATE-v1",
        "registry": str(registry_path.relative_to(ROOT)),
        "group_order": list(GROUPS),
        "scalar_kappaS2_totals": [fmt(x) for x in scalar_dynkin_totals(fields)],
        "fermion_kappaS2_totals": [fmt(x) for x in fermion_dynkin_totals(fields)],
        "derived_one_loop": [fmt(x) for x in derived_one],
        "derived_two_loop": [[fmt(x) for x in row] for row in derived_two],
        "expected_one_loop": [fmt(x) for x in expected_one],
        "expected_two_loop_2020": [[fmt(x) for x in row] for row in expected_two],
        "gates": gates,
        "overall": "PASS"
        if gates["one_loop_exact_match"] == gates["two_loop_exact_match_2020"] == gates["b_L4_is_525_over_2"] == "PASS"
        else "FAIL",
        "epistemic_status": "independent algebraic derivation from frozen field content and generic beta-function formulas; Yukawa gauge-beta terms intentionally excluded",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = calculate(args.registry)
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")
    if result["overall"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
