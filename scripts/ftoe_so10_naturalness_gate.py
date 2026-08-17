"""Naturalness gate for the FToE informational-scalar hierarchy.

The verified gauge-only G422 solution fixes M_U independently.  This gate asks
whether a TeV-scale informational scalar can remain light when it is embedded
in an ordinary SO(10) scalar multiplet coupled to the GUT-breaking sector.

For any complex scalar I and breaking scalar Phi, the norm portal
    (I^dagger I)(Phi^dagger Phi)
is gauge invariant and invariant under ordinary phase symmetries acting on I.
After <Phi> ~ M_U it induces delta(mu_I^2) ~ lambda_portal M_U^2.  Therefore a
Planck-suppressed dimension-13 contribution cannot be the leading origin of
mu_I unless this renormalizable portal and analogous mass/mixing terms are
removed by a stronger mechanism (e.g. an exact/collective Goldstone symmetry,
sequestering, or another explicitly demonstrated protection mechanism).

The one-loop gauge proxy g_U^4/(16 pi^2) is reported only as an order-of-
magnitude radiative-stability diagnostic; representation-dependent coefficients
are not assumed to be one.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class NaturalnessResult:
    schema: str
    M_U_GeV: float
    mu_I_GeV: float
    alpha_U: float
    required_portal_max: float
    tuning_inverse: float
    g_U: float
    gauge_loop_proxy: float
    loop_proxy_over_required_portal: float
    gates: dict[str, str]
    simple_embedded_doublet_status: str
    protected_pNGB_or_sequestered_branch_status: str
    scientific_status: str
    notes: list[str]


def calculate(m_u: float, mu_i: float, alpha_u: float) -> NaturalnessResult:
    if not (m_u > 0.0 and mu_i > 0.0 and alpha_u > 0.0):
        raise ValueError("all inputs must be positive")
    if mu_i >= m_u:
        raise ValueError("mu_I must lie below M_U")

    required = (mu_i / m_u) ** 2
    tuning_inverse = 1.0 / required
    g_u = math.sqrt(4.0 * math.pi * alpha_u)
    gauge_loop_proxy = g_u**4 / (16.0 * math.pi**2)
    loop_ratio = gauge_loop_proxy / required

    gates = {
        "renormalizable_norm_portal_is_gauge_invariant": "PASS",
        "ordinary_phase_symmetry_forbids_norm_portal": "FAIL",
        "required_portal_is_order_one": "FAIL" if required < 0.1 else "PASS",
        "generic_embedded_doublet_natural_without_extra_protection": "FAIL",
        "explicit_collective_or_shift_symmetry_protection": "NOT_TESTED",
        "radiative_stability_of_protection": "NOT_TESTED",
        "dimension13_term_can_dominate_after_renormalizable_terms_removed": "REVIEW",
    }

    return NaturalnessResult(
        schema="FTOE-SO10-NATURALNESS-GATE-v0.1",
        M_U_GeV=m_u,
        mu_I_GeV=mu_i,
        alpha_U=alpha_u,
        required_portal_max=required,
        tuning_inverse=tuning_inverse,
        g_U=g_u,
        gauge_loop_proxy=gauge_loop_proxy,
        loop_proxy_over_required_portal=loop_ratio,
        gates=gates,
        simple_embedded_doublet_status="FAIL",
        protected_pNGB_or_sequestered_branch_status="REVIEW",
        scientific_status="REVIEW",
        notes=[
            "The FAIL applies to an ordinary embedded doublet with no additional protection mechanism.",
            "A phase Z_N cannot forbid (I^dagger I)(Phi^dagger Phi) because both norm bilinears are neutral.",
            "The gauge-loop proxy is diagnostic only; an exact coefficient requires the chosen SO(10) representations and full scalar potential.",
            "L1 can remain viable only on a separately demonstrated protected branch whose renormalizable mass and portal operators are absent or symmetry-controlled.",
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--MU", type=float, default=2.04990990688745e16)
    parser.add_argument("--muI", type=float, default=9.54e3)
    parser.add_argument("--alphaU", type=float, default=0.032067325570772874)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = calculate(args.MU, args.muI, args.alphaU)
    text = json.dumps(asdict(result), indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
