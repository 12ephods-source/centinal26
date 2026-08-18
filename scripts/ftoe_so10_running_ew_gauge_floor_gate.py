"""RG-improved electroweak gauge-floor naturalness gate for the frozen FToE I doublet.

This removes the fixed-coupling approximation from ftoe_so10_ew_gauge_floor_gate.py.
It uses the already frozen one-loop low-energy running in ftoe_so10_422_gate.py:
SM beta coefficients below m_I=sqrt(2)*mu_I and SM+I coefficients above that
threshold.  The break-even cutoff Lambda_* is defined implicitly by

    Lambda_*^2 C_gauge(Lambda_*)/(16 pi^2) = mu_I^2,
    C_gauge(mu) = (9/4) g_2(mu)^2 + (3/4) g_Y(mu)^2.

The one-loop Wilsonian mass-sensitivity coefficient follows the standard
Veltman-condition convention; the running is a deterministic refinement of the
existing frozen branch, not a new protection mechanism.

Primary sources / calculation basis:
- Mihaila, Salomon, Steinhauser, arXiv:1201.5868: SM gauge-coupling RG functions.
- Masina and Quiros, arXiv:1308.1242, Eqs. (2),(11),(12): one-loop quadratic
  sensitivity and gauge contribution (9/4)g^2+(3/4)g'^2.

This remains a Wilsonian naturalness diagnostic, not a regulator-independent
no-go theorem.  A future explicit collective/SUSY/composite/sequestered branch
must compute its own cancellations and cannot be promoted by this gate.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from scripts.ftoe_so10_422_gate import (
    MZ,
    M_I_PHYS,
    MU_I,
    low_energy_couplings,
)

GUT_SCALE_REFERENCE_GEV = 2.04990990688745e16


@dataclass(frozen=True)
class RunningGaugeFloorResult:
    schema: str
    mu_I_GeV: float
    informational_threshold_GeV: float
    cutoff_max_GeV: float
    cutoff_max_TeV: float
    alpha1_inv_at_cutoff: float
    alpha2_inv_at_cutoff: float
    g2_at_cutoff: float
    gY_at_cutoff: float
    C_gauge_at_cutoff: float
    fixed_mz_cutoff_reference_GeV: float
    rg_shift_percent: float
    gut_scale_reference_GeV: float
    gut_to_cutoff_ratio: float
    gut_scale_mass_correction_over_mu2: float
    current_frozen_branch_status: str
    scientific_gate_status: str
    assumptions: list[str]
    sources: list[str]


def gauge_coefficient(mu: float) -> tuple[float, float, float, float, float]:
    if mu < MZ:
        raise ValueError("mu must be >= MZ")
    a_inv = low_energy_couplings(mu)
    alpha1 = 1.0 / a_inv["1"]
    alpha2 = 1.0 / a_inv["2"]
    alpha_y = (3.0 / 5.0) * alpha1  # alpha_1=(5/3)alpha_Y
    g2 = math.sqrt(4.0 * math.pi * alpha2)
    gy = math.sqrt(4.0 * math.pi * alpha_y)
    coeff = (9.0 / 4.0) * g2 * g2 + (3.0 / 4.0) * gy * gy
    return a_inv["1"], a_inv["2"], g2, gy, coeff


def residual(cutoff: float, mu_i: float = MU_I) -> float:
    if cutoff <= 0.0 or mu_i <= 0.0:
        raise ValueError("cutoff and mu_i must be positive")
    coeff = gauge_coefficient(cutoff)[-1]
    return cutoff * cutoff * coeff / (16.0 * math.pi * math.pi) - mu_i * mu_i


def solve_break_even(
    mu_i: float = MU_I,
    lo: float = M_I_PHYS,
    hi: float = 1.0e7,
    iterations: int = 180,
) -> float:
    if mu_i <= 0.0 or lo < MZ or hi <= lo:
        raise ValueError("invalid break-even bracket")
    flo = residual(lo, mu_i)
    fhi = residual(hi, mu_i)
    if flo == 0.0:
        return lo
    if fhi == 0.0:
        return hi
    if flo * fhi > 0.0:
        raise ValueError("break-even root is not bracketed")

    # Bisect in log(mu), appropriate for scale equations spanning decades.
    xlo, xhi = math.log(lo), math.log(hi)
    for _ in range(iterations):
        xm = 0.5 * (xlo + xhi)
        m = math.exp(xm)
        fm = residual(m, mu_i)
        if flo * fm <= 0.0:
            xhi = xm
        else:
            xlo, flo = xm, fm
    return math.exp(0.5 * (xlo + xhi))


def calculate(
    mu_i: float = MU_I,
    gut_scale: float = GUT_SCALE_REFERENCE_GEV,
) -> RunningGaugeFloorResult:
    if mu_i <= 0.0 or gut_scale <= 0.0:
        raise ValueError("mu_i and gut_scale must be positive")

    cutoff = solve_break_even(mu_i=mu_i)
    a1i, a2i, g2, gy, coeff = gauge_coefficient(cutoff)

    # Previous frozen-MZ-coupling result, retained only as a regression reference.
    mz_coeff = gauge_coefficient(MZ)[-1]
    fixed_cutoff = 4.0 * math.pi * mu_i / math.sqrt(mz_coeff)
    rg_shift = 100.0 * (cutoff / fixed_cutoff - 1.0)
    ratio = gut_scale / cutoff

    return RunningGaugeFloorResult(
        schema="FTOE-SO10-RUNNING-EW-GAUGE-FLOOR-v0.1",
        mu_I_GeV=mu_i,
        informational_threshold_GeV=M_I_PHYS,
        cutoff_max_GeV=cutoff,
        cutoff_max_TeV=cutoff / 1.0e3,
        alpha1_inv_at_cutoff=a1i,
        alpha2_inv_at_cutoff=a2i,
        g2_at_cutoff=g2,
        gY_at_cutoff=gy,
        C_gauge_at_cutoff=coeff,
        fixed_mz_cutoff_reference_GeV=fixed_cutoff,
        rg_shift_percent=rg_shift,
        gut_scale_reference_GeV=gut_scale,
        gut_to_cutoff_ratio=ratio,
        gut_scale_mass_correction_over_mu2=ratio * ratio,
        current_frozen_branch_status="FAIL",
        scientific_gate_status="FAIL",
        assumptions=[
            "I is the frozen linearly realized complex electroweak doublet with Y=1/2.",
            "One-loop gauge running uses the frozen SM coefficients below m_I and SM+I coefficients above m_I.",
            "No partner, collective, SUSY, composite, or sequestered cancellation is present in the frozen branch.",
            "This is a Wilsonian one-loop naturalness diagnostic, not a regulator-independent theorem.",
        ],
        sources=[
            "Mihaila-Salomon-Steinhauser arXiv:1201.5868 (SM gauge RG functions)",
            "Masina-Quiros arXiv:1308.1242 Eqs. (2),(11),(12) (quadratic sensitivity and gauge coefficient)",
            "scripts/ftoe_so10_422_gate.py (frozen thresholds and beta coefficients)",
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--muI", type=float, default=MU_I)
    parser.add_argument("--gut-scale", type=float, default=GUT_SCALE_REFERENCE_GEV)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = calculate(args.muI, args.gut_scale)
    text = json.dumps(asdict(result), indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
