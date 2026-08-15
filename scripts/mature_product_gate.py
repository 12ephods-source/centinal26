from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    evidence: dict[str, Any]
    reason: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def evaluate_host(host: dict[str, Any]) -> list[GateResult]:
    return [
        GateResult(
            "functional",
            bool(host.get("functional_pass")),
            {"functional_pass": host.get("functional_pass")},
            "functional suite must pass",
        ),
        GateResult(
            "regression",
            bool(host.get("regression_pass")),
            {"regression_pass": host.get("regression_pass")},
            "retained regression suite must pass",
        ),
        GateResult(
            "recovery",
            bool(host.get("rollback_verified")),
            {"rollback_verified": host.get("rollback_verified")},
            "rollback/recovery path must be verified",
        ),
    ]


def evaluate_physical(device: dict[str, Any] | None) -> list[GateResult]:
    if device is None:
        return [
            GateResult(
                "physical_device",
                False,
                {},
                "BLOCKED_EXTERNAL: no Android/Termux evidence supplied",
            )
        ]

    boot_changed = (
        bool(device.get("pre_boot_id"))
        and bool(device.get("post_boot_id"))
        and device.get("pre_boot_id") != device.get("post_boot_id")
    )
    checks = [
        ("platform", device.get("platform") == "android/termux"),
        ("fresh_heartbeat", bool(device.get("fresh_heartbeat"))),
        ("bounded_job_completed", bool(device.get("bounded_job_completed"))),
        ("independent_verification", bool(device.get("independent_verification"))),
        ("forbidden_capability_rejected", bool(device.get("forbidden_capability_rejected"))),
        ("boot_id_changed", boot_changed),
        ("post_reboot_heartbeat", bool(device.get("post_reboot_heartbeat"))),
        ("endurance_pass", bool(device.get("endurance_pass"))),
    ]
    passed = all(value for _, value in checks)
    return [
        GateResult(
            "physical_device",
            passed,
            {name: value for name, value in checks},
            "all Android/Termux maturity checks must pass",
        )
    ]


def evaluate(
    host: dict[str, Any],
    device: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gates = evaluate_host(host) + evaluate_physical(device)
    all_pass = all(gate.passed for gate in gates)
    if all_pass:
        status = "MATURE"
    elif device is None:
        status = "BLOCKED_EXTERNAL"
    else:
        status = "NOT_MATURE"
    return {
        "schema": "frost.mature_product_gate/v1",
        "status": status,
        "hard_gate_pass": all_pass,
        "gates": [asdict(gate) for gate in gates],
    }


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Frost mature-product hard gates.")
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--device", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("mature-product-result.json"),
    )
    parser.add_argument("--require-mature", action="store_true")
    args = parser.parse_args()

    host = load_json(args.host)
    device = load_json(args.device) if args.device else None
    result = evaluate(host, device)
    result["host_sha256"] = sha256_file(args.host)
    result["device_sha256"] = sha256_file(args.device) if args.device else None
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))
    if args.require_mature and result["status"] != "MATURE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
