from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "kms_modular_cocycle_scan", HERE / "kms_modular_cocycle_scan.py"
)
assert SPEC is not None and SPEC.loader is not None
harness = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = harness
SPEC.loader.exec_module(harness)


class KMSModularCocycleHarnessTests(unittest.TestCase):
    def test_reference_modular_equals_negative_beta_static_flow(self) -> None:
        a, _, hamiltonian = harness.oscillator(4, 1.03)
        rho0 = harness.thermal(hamiltonian, harness.BETA)
        x = (a + a.conj().T) / np.sqrt(2.0)
        for s in harness.S_SCAN:
            self.assertLess(
                harness.nr(
                    harness.sigma(rho0, s, x),
                    harness.alpha(hamiltonian, -harness.BETA * s, x),
                ),
                1.0e-12,
            )

    def test_normalized_trace_modular_flow_is_trivial(self) -> None:
        a = harness.annihilation(5)
        x = a + a.conj().T
        rho_trace = np.eye(5, dtype=complex) / 5.0
        self.assertLess(harness.nr(harness.sigma(rho_trace, 0.37, x), x), 1.0e-12)

    def test_cocycle_identity_and_intertwining(self) -> None:
        a, _, hamiltonian = harness.oscillator(5, 1.03)
        x = (a + a.conj().T) / np.sqrt(2.0)
        rho0 = harness.thermal(hamiltonian, harness.BETA)
        d = harness.displace(5, 0.12 * (0.31 + 0.17j))
        rho = d @ rho0 @ d.conj().T
        s, t = 0.23, -0.17
        u_s = harness.cocycle(rho, rho0, s)
        lhs = harness.cocycle(rho, rho0, s + t)
        rhs = u_s @ harness.sigma(rho0, s, harness.cocycle(rho, rho0, t))
        self.assertLess(harness.nr(lhs, rhs), 1.0e-12)
        self.assertLess(
            harness.nr(
                harness.sigma(rho, s, x),
                u_s @ harness.sigma(rho0, s, x) @ u_s.conj().T,
            ),
            1.0e-12,
        )

    def test_relative_entropy_energy_identity(self) -> None:
        for epsilon in (0.2, 0.05, -0.05):
            totals = harness.coherent_totals(5, epsilon)
            self.assertLess(abs(totals["S"] - harness.BETA * totals["dE"]), 1.0e-11)

    def test_bkm_analytic_baseline_without_fit(self) -> None:
        result = harness.bkm_scan()
        self.assertFalse(result["normalization_fitted"])
        self.assertLess(result["n_cut_5_max_bkm_relative_error"], 1.0e-7)
        self.assertLess(
            result["n_cut_5_epsilon_0.05_to_0.025_refinement_relative_change"],
            1.0e-7,
        )

    def test_positive_energy_clock_uses_smeared_effect(self) -> None:
        result = harness.clock_metrics()
        self.assertEqual(result["q_min"], 0.0)
        self.assertFalse(result["uses_distributional_time_projector"])
        self.assertTrue(result["uses_smeared_povm_effect"])
        self.assertGreaterEqual(result["minimum_effect_eigenvalue"], -1.0e-12)
        self.assertLess(result["endpoint_free_povm_closure_residual"], 1.0e-12)

    def test_scope_blocks_gravitational_promotion(self) -> None:
        report = harness.run_harness()
        self.assertEqual(report["gate_accounting"]["Gate_5"], "PROPOSED")
        self.assertEqual(report["gate_accounting"]["Gate_6"], "PROPOSED")
        self.assertEqual(
            report["gate_accounting"]["higher_order_reconstruction"],
            "OPEN_SEPARATE_GATE",
        )
        self.assertEqual(
            report["scope"]["algebra_type_of_numerical_model"],
            "Type I matrix algebra only",
        )

    def test_strict_report_passes_all_finite_gates(self) -> None:
        report = harness.run_harness()
        self.assertEqual(
            report["status"],
            "PASS_FINITE_TYPE_I_KMS_MODULAR_COCYCLE_BASELINE",
        )
        self.assertTrue(all(report["gates"].values()))


if __name__ == "__main__":
    unittest.main()