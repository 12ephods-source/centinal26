from __future__ import annotations

import argparse
import json
import py_compile
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rc4_successor_common import candidate_digest, candidate_manifest, write_json

PROVENANCE_CLASS = "RECONSTRUCTED_SUCCESSOR"


def qualify(candidate_root: Path, output_report: Path) -> dict[str, Any]:
    manifest = candidate_manifest(candidate_root)
    digest = candidate_digest(candidate_root)
    errors: list[dict[str, str]] = []
    checks: list[dict[str, object]] = []

    for item in manifest["files"]:
        rel = str(item["path"])
        path = candidate_root / rel
        suffix = path.suffix.lower()
        try:
            if suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))
                checks.append({"path": rel, "check": "json-parse", "status": "PASS"})
            elif suffix == ".py":
                py_compile.compile(str(path), doraise=True)
                checks.append({"path": rel, "check": "python-compile", "status": "PASS"})
            elif suffix == ".sh":
                proc = subprocess.run(
                    ["bash", "-n", str(path)],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if proc.returncode != 0:
                    raise ValueError(proc.stderr.strip() or f"bash -n returned {proc.returncode}")
                checks.append({"path": rel, "check": "bash-syntax", "status": "PASS"})
        except (OSError, ValueError, json.JSONDecodeError, py_compile.PyCompileError, subprocess.SubprocessError) as exc:
            errors.append({"path": rel, "error": str(exc)})
            checks.append({"path": rel, "check": "static-host-check", "status": "FAIL"})

    report = {
        "format": "automation-rc4-host-qualification-successor-v1",
        "provenance_class": PROVENANCE_CLASS,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "PASS" if not errors else "FAIL",
        "candidate_tree_root_sha256": digest,
        "candidate_manifest_sha256": manifest.get("candidate_tree_root_sha256"),
        "physical_android_validated": False,
        "scope": "static host qualification only",
        "checks": checks,
        "errors": errors,
        "limitations": [
            "Candidate application code is compiled or syntax-checked but not executed by this successor harness.",
            "Host qualification does not satisfy Android, endurance, device-sync, recovery, native-certification, or promotion gates.",
            "This is a reconstructed successor, not the unrecovered original host qualification harness.",
        ],
    }
    write_json(output_report, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="RC4 static host-qualification successor")
    parser.add_argument("candidate_root", type=Path)
    parser.add_argument("output_report", type=Path)
    args = parser.parse_args()
    try:
        report = qualify(args.candidate_root, args.output_report)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
