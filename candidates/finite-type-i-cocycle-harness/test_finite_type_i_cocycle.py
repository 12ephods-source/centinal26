#!/usr/bin/env python3
from __future__ import annotations

import math
import unittest

import numpy as np

import finite_type_i_cocycle as coc


class SpectralStateTests(unittest.TestCase):
    def test_floor_free_extreme_thermal_log_weights(self) -> None:
        logs = coc.normalized_thermal_log_weights(16, 2 * math.pi, 3.7)
        self.assertLess(float(np.min(logs)), -300.0)
        self.assertLess(float(np.min(logs)), math.log(1e-15))
        state = coc.thermal_state(16, 2 * math.pi, 3.7, "extreme")
        log_rho = state.log_matrix()
        self.assertTrue(np.all(np.isfinite(log_rho)))
        self.assertAlmostEqual(float(np.trace(state.density()).real), 1.0, places=12)

    def test_displacement_is_unitary(self) -> None:
        u = coc.displacement(12, 0.17 - 0.11j)
        ident = np.eye(12, dtype=complex)
        self.assertLess(coc.relative_fro_residual(u.conj().T @ u, ident), 1e-12)


class CocycleIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.psi = coc.thermal_state(8, 2 * math.pi, 1.03, "psi")
        self.phi = coc.displaced_thermal_state(8, 2 * math.pi, 1.03, 0.1 + 0.03j, "phi")
        self.chi = coc.displaced_thermal_state(8, 2 * math.pi, 1.03, -0.08 + 0.02j, "chi")

    def test_unitarity(self) -> None:
        ident = np.eye(8, dtype=complex)
        for s in coc.S_VALUES:
            u = coc.connes_cocycle(self.phi, self.psi, s)
            self.assertLess(coc.relative_fro_residual(u.conj().T @ u, ident), 2e-12)

    def test_cocycle_identity(self) -> None:
        for s, t in coc.PAIR_VALUES:
            lhs = coc.connes_cocycle(self.phi, self.psi, s + t)
            rhs = coc.connes_cocycle(self.phi, self.psi, s) @ coc.modular_flow(
                self.psi, coc.connes_cocycle(self.phi, self.psi, t), s
            )
            self.assertLess(coc.relative_fro_residual(lhs, rhs), 5e-12)

    def test_chain_rule(self) -> None:
        for s in (-0.4, 0.2, 0.5):
            lhs = coc.connes_cocycle(self.phi, self.chi, s)
            rhs = coc.connes_cocycle(self.phi, self.psi, s) @ coc.connes_cocycle(
                self.psi, self.chi, s
            )
            self.assertLess(coc.relative_fro_residual(lhs, rhs), 5e-12)

    def test_modular_intertwining(self) -> None:
        x = coc.deterministic_observables(8)["H_random"]
        for s in coc.S_VALUES:
            u = coc.connes_cocycle(self.phi, self.psi, s)
            lhs = coc.modular_flow(self.phi, x, s)
            rhs = u @ coc.modular_flow(self.psi, x, s) @ u.conj().T
            self.assertLess(coc.relative_fro_residual(lhs, rhs), 5e-12)

    def test_state_transport_at_minus_i_over_2(self) -> None:
        for obs in coc.deterministic_observables(8).values():
            self.assertLess(coc.state_transport_residual(self.phi, self.psi, obs), 5e-10)

    def test_relative_entropy_nonnegative(self) -> None:
        self.assertGreaterEqual(coc.relative_entropy(self.phi, self.psi), -5e-12)
        self.assertGreaterEqual(coc.relative_entropy(self.psi, self.phi), -5e-12)

    def test_generator(self) -> None:
        self.assertLess(coc.generator_residual(self.phi, self.psi), 2e-8)


class FullHarnessTests(unittest.TestCase):
    def test_strict_gate(self) -> None:
        report = coc.run()
        self.assertTrue(report["gates"]["all_pass"], report["gates"])
        self.assertEqual(report["status"], "PASS_FINITE_TYPE_I_COCYCLE_CONSISTENCY")


if __name__ == "__main__":
    unittest.main()
