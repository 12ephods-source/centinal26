"""Independent electroweak gauge-floor naturalness gate for the FToE I doublet.

This gate does not use the scalar norm portal or the earlier unified-coupling
proxy.  It uses only the frozen electroweak gauge inputs already present in
ftoe_so10_422_gate.py and the standard one-loop Veltman gauge contribution
for a complex SU(2)_L doublet with Y=1/2,

    delta m_I^2 = Lambda^2/(16 pi^2) * C_gauge,
    C_gauge = (9/4) g_2^2 + (3/4) g_Y^2,

when no additional partner/cancellation mechanism is present.

Reference for the one-loop coefficient and cutoff sensitivity:
I. Masina and M. Quiros, arXiv:1308.1242, Eqs. (2), (11), (12).

The result is a Wilsonian naturalness diagnostic, not a regulator-independent
no-go theorem.  Nonlinear collective cancellation, supersymmetry, compositeness,
or another explicitly frozen cancellation mechanism can invalidate the simple
single-doublet estimate; none is present in the current frozen branch.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

ALPHA1_INV_MZ = 59.01  # SU(5)-normalized alpha_1, frozen in ftoe_so10_422_gate.py
ALPHA2_INV_MZ = 29.59
MU_I_GEV = 9.54e3


@dataclass(frozen=True)
class GaugeFloorResult:
    schema: str
    alpha1_inv_mz: float
    alpha2_inv_mz: float
    g2_mz: float
    gY_mz: float
    C_gauge: float
    mu_I_GeV: float
    cutoff_max_GeV: float
    cutoff_max_TeV: float
    gut_scale_reference_GeV: float
    gut_to_cutoff_ratio: float
    gut_scale_mass_correction_over_mu2: float
    current_frozen_branch_status: str
    scientific_gate_status: str
    assumptions: list[str]
    source: str


def calculate(
    alpha1_inv: float = ALPHA1_INV_MZ,
    alpha2_inv: float = ALPHA2_INV_MZ,
    mu_i: float = MU_I_GEV,
    gut_scale: float = 2.04990990688745e16,
) -> GaugeFloorResult:
    if min(alpha1_inv, alpha2_inv, mu_i, gut_scale) <= 0.0:
        raise ValueError("all inputs must be positive")

    # alpha_1 = (5/3) alpha_Y, hence alpha_Y = (3/5) alpha_1.
    alpha1 = 1.0 / alpha1_inv
    alpha2 = 1.0 / alpha2_inv
    alpha_y = (3.0 / 5.0) * alpha1
    g2 = math.sqrt(4.0 * math.pi * alpha2)
    gy = math.sqrt(4.0 * math.pi * alpha_y)

    c_gauge = (9.0 / 4.0) * g2 * g2 + (3.0 / 4.0) * gy * gy
    cutoff_max = 4.0 * math.pi * mu_i / math.sqrt(c_gauge)
    ratio = gut_scale / cutoff_max
    correction_ratio = (ratio * ratio)

    return GaugeFloorResult(
        schema="FTOE-SO10-EW-GAUGE-FLOOR-v0.1",
        alpha1_inv_mz=alpha1_inv,
        alpha2_inv_mz=alpha2_inv,
        g2_mz=g2,
        gY_mz=gy,
        C_gauge=c_gauge,
        mu_I_GeV=mu_i,
        cutoff_max_GeV=cutoff_max,
        cutoff_max_TeV=cutoff_max / 1.0e3,
        gut_scale_reference_GeV=gut_scale,
        gut_to_cutoff_ratio=ratio,
        gut_scale_mass_correction_over_mu2=correction_ratio,
        current_frozen_branch_status="FAIL",
        scientific_gate_status="FAIL",
        assumptions=[
            "I is the current linearly realized electroweak complex doublet with Y=1/2.",
            "No additional symmetry-enforced partner cancellation is present in the frozen branch.",
            "The estimate is a one-loop Wilsonian naturalness diagnostic; it is not claimed as a regulator-independent theorem.",
            "A future nonlinear/collective/SUSY/composite/sequestered mechanism must be versioned explicitly and re-evaluated rather than inferred from this result.",
        ],
        source="Masina-Quirós arXiv:1308.1242 Eqs. (2),(11),(12); electroweak inputs frozen in scripts/ftoe_so10_422_gate.py",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alpha1-inv", type=float, default=ALPHA1_INV_MZ)
    parser.add_argument("--alpha2-inv", type=float, default=ALPHA2_INV_MZ)
    parser.add_argument("--muI", type=float, default=MU_I_GEV)
    parser.add_argument("--gut-scale", type=float, default=2.04990990688745e16)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = calculate(args.alpha1_inv, args.alpha2_inv, args.muI, args.gut_scale)
    text = json.dumps(asdict(result), indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
