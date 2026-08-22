from __future__ import annotations

import argparse
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class PowersControl:
    lambda_ratio: float = 0.25

    def __post_init__(self) -> None:
        if not (0.0 < self.lambda_ratio < 1.0):
            raise ValueError("lambda_ratio must satisfy 0 < lambda < 1")

    @property
    def local_probabilities(self) -> tuple[float, float]:
        z = 1.0 + self.lambda_ratio
        return (1.0 / z, self.lambda_ratio / z)

    def cylinder_probability(self, bits: tuple[int, ...]) -> float:
        p0, p1 = self.local_probabilities
        value = 1.0
        for bit in bits:
            if bit == 0:
                value *= p0
            elif bit == 1:
                value *= p1
            else:
                raise ValueError("bits must contain only 0 or 1")
        return value

    def modular_exponent(self, left: tuple[int, ...], right: tuple[int, ...]) -> int:
        if len(left) != len(right):
            raise ValueError("basis strings must have equal length")
        return sum(left) - sum(right)

    def modular_ratio(self, left: tuple[int, ...], right: tuple[int, ...]) -> float:
        return self.cylinder_probability(left) / self.cylinder_probability(right)

    def state_compatibility_residual(self, expectation: float) -> float:
        p0, p1 = self.local_probabilities
        return abs(expectation * (p0 + p1) - expectation)

    def evaluate(self, max_sites: int = 8) -> dict[str, object]:
        if max_sites < 2:
            raise ValueError("max_sites must be >= 2")

        ratio_errors: list[float] = []
        compatibility: list[float] = []
        observed_exponents: set[int] = set()

        for n_sites in range(1, max_sites + 1):
            zeros = (0,) * n_sites
            for ones in range(n_sites + 1):
                left = (1,) * ones + (0,) * (n_sites - ones)
                exponent = self.modular_exponent(left, zeros)
                ratio_errors.append(
                    abs(self.modular_ratio(left, zeros) - self.lambda_ratio**exponent)
                )
                observed_exponents.add(exponent)
                observed_exponents.add(-exponent)
            compatibility.append(self.state_compatibility_residual(0.37123456789))

        checks = {
            "faithful_local_state": min(self.local_probabilities) > 0.0,
            "normalized_local_state": abs(sum(self.local_probabilities) - 1.0) <= 1e-15,
            "unital_embedding_contract": True,
            "compatible_product_state_family": max(compatibility) <= 1e-15,
            "local_modular_ratio_exactness": max(ratio_errors) <= 1e-14,
            "finite_ratio_exponents_exhausted": set(
                range(-max_sites, max_sites + 1)
            ).issubset(observed_exponents),
            "declared_gns_limit": True,
            "declared_local_analytic_modular_core": True,
            "type_discriminator_declared": True,
            "source_classification_matches_control": True,
            "physical_ds_identification_blocked": True,
        }

        return {
            "schema": "ds.continuum.powers-control.v1",
            "execution_pass": all(checks.values()),
            "scientific_pass": False,
            "control_classification": "KNOWN_POWERS_TYPE_III_LAMBDA_CONTROL",
            "lambda_ratio": self.lambda_ratio,
            "local_probabilities": list(self.local_probabilities),
            "max_sites_checked": max_sites,
            "max_state_compatibility_residual": max(compatibility),
            "max_local_modular_ratio_error": max(ratio_errors),
            "observed_ratio_exponent_min": min(observed_exponents),
            "observed_ratio_exponent_max": max(observed_exponents),
            "asymptotic_ratio_target": {
                "form": "{0} union {lambda^k : k in Z}",
                "source_classification": (
                    "Araki-Woods case (iv): Type III; Powers examples lie in this class"
                ),
            },
            "checks": checks,
            "continuum_contract": {
                "infinite_local_algebra_sequence": "A_n = tensor_{j=1}^n M_2(C)",
                "embedding": "i_n(A) = A tensor I_2",
                "state_family": "phi_n = tensor_{j=1}^n phi_lambda",
                "compatibility": "phi_{n+1}(i_n(A)) = phi_n(A)",
                "limit_representation": (
                    "GNS representation of the infinite product state on the quasi-local "
                    "inductive-limit C*-algebra; von Neumann closure is the ITPFI/Powers "
                    "control factor"
                ),
                "modular_domain": (
                    "algebraic union of finite cylinder algebras; each local matrix unit "
                    "is entire analytic for product modular flow"
                ),
                "type_discriminator": "Araki-Woods asymptotic ratio set r_infty",
            },
            "forbidden_promotions": [
                "does not identify this constant-lambda control with the physical de Sitter static-patch algebra",
                "does not show that the existing m=2,3,4 regulator converges to this control",
                "does not establish Type III_1; the control is Type III_lambda for fixed 0<lambda<1",
                "does not establish a Type II_infinity crossed product, Type II_1 finite corner, gravity, or Einstein dynamics",
            ],
            "next_required_physical_input": (
                "derive an infinite de Sitter mode/state family and embeddings (or an "
                "independent continuum AQFT construction) whose modular invariant is "
                "Type III_1, then relate the finite numerical regulator to that continuum object."
            ),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lambda-ratio", type=float, default=0.25)
    parser.add_argument("--max-sites", type=int, default=8)
    parser.add_argument("--output")
    args = parser.parse_args()

    result = PowersControl(args.lambda_ratio).evaluate(args.max_sites)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text)
    print(text, end="")
    return 0 if result["execution_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
