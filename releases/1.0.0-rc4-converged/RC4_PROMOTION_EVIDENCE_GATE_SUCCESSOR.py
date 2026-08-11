from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rc4_successor_common import candidate_digest, sha256_file, write_json

PROVENANCE_CLASS = "RECONSTRUCTED_SUCCESSOR"
REQUIRED = {
    "ANDROID_VALIDATION",
    "ENDURANCE_VALIDATION",
    "DEVICE_SYNC_VALIDATION",
    "RECOVERY_DRILL",
}


def _kind(record: dict[str, Any]) -> str:
    return str(
        record.get("evidence_type")
        or record.get("validation_type")
        or record.get("kind")
        or record.get("type")
        or ""
    ).upper()


def _is_android_termux(record: dict[str, Any]) -> bool:
    platform = str(record.get("platform", "")).lower()
    android = record.get("android_detected") is True or record.get("android") is True or "android" in platform
    termux = record.get("termux_detected") is True or record.get("termux") is True or "termux" in platform
    return android and termux


def _attested(record: dict[str, Any]) -> bool:
    return record.get("attestation_verified") is True or record.get("device_attestation_verified") is True


def gate(candidate_root: Path, evidence_dir: Path) -> dict[str, Any]:
    digest = candidate_digest(candidate_root)
    records: dict[str, list[tuple[Path, dict[str, Any]]]] = {kind: [] for kind in REQUIRED}
    parse_errors: list[str] = []

    for path in sorted(evidence_dir.rglob("*.json")):
        if path.name == "RC4_PROMOTION_EVIDENCE_GATE.json":
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            parse_errors.append(f"{path}: {exc}")
            continue
        kind = _kind(record)
        if kind in records:
            records[kind].append((path, record))

    errors = list(parse_errors)
    selected: dict[str, dict[str, Any]] = {}
    for kind in sorted(REQUIRED):
        matches = records[kind]
        if len(matches) != 1:
            errors.append(f"{kind}: expected exactly one evidence record, found {len(matches)}")
            continue
        path, record = matches[0]
        selected[kind] = {
            "path": str(path.resolve()),
            "sha256": sha256_file(path),
        }
        status = str(record.get("status") or record.get("overall") or "").upper()
        if status != "PASS":
            errors.append(f"{kind}: status is not PASS")
        if record.get("candidate_tree_root_sha256") != digest:
            errors.append(f"{kind}: candidate digest mismatch")
        if record.get("private_keys_exported") is True:
            errors.append(f"{kind}: private_keys_exported must not be true")

        if kind in {"ANDROID_VALIDATION", "ENDURANCE_VALIDATION", "DEVICE_SYNC_VALIDATION"}:
            if not _attested(record):
                errors.append(f"{kind}: verified device attestation is required")
            if record.get("physical_android_validated") is not True:
                errors.append(f"{kind}: physical_android_validated must be true")
            if not _is_android_termux(record):
                errors.append(f"{kind}: Android + Termux detection is required")

        if kind == "ENDURANCE_VALIDATION":
            samples = record.get("successful_samples")
            elapsed = record.get("elapsed_seconds")
            if not isinstance(samples, (int, float)) or samples < 60:
                errors.append("ENDURANCE_VALIDATION: at least 60 successful samples are required")
            if not isinstance(elapsed, (int, float)) or elapsed < 3600:
                errors.append("ENDURANCE_VALIDATION: at least 3600 elapsed seconds are required")
            if record.get("unrecovered_jobs", 0) not in {0, None}:
                errors.append("ENDURANCE_VALIDATION: unrecovered_jobs must be zero")

        if kind == "DEVICE_SYNC_VALIDATION":
            signed_verified = record.get("signed_bundle_verified") is True or record.get("signature_verified") is True
            peer_pinned = record.get("peer_key_pinned") is True or record.get("trusted_peer_verified") is True
            if not signed_verified:
                errors.append("DEVICE_SYNC_VALIDATION: signed bundle verification is required")
            if not peer_pinned:
                errors.append("DEVICE_SYNC_VALIDATION: trusted/pinned peer verification is required")

        if kind == "RECOVERY_DRILL":
            if record.get("restore_verified") is not True:
                errors.append("RECOVERY_DRILL: restore_verified must be true")
            if record.get("rollback_verified") is not True:
                errors.append("RECOVERY_DRILL: rollback_verified must be true")

    report = {
        "format": "automation-rc4-promotion-evidence-gate-successor-v1",
        "provenance_class": PROVENANCE_CLASS,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "PASS" if not errors else "BLOCK",
        "candidate_tree_root_sha256": digest,
        "required_evidence": sorted(REQUIRED),
        "selected_evidence": selected,
        "errors": errors,
        "promotion_performed": False,
        "limitations": [
            "This successor validates the outer evidence contract; native candidate certification remains a separate gate.",
            "Attestation verification flags must come from the trusted import/verification boundary; this tool does not validate Ed25519 archives itself.",
            "A PASS here is not GA promotion.",
        ],
    }
    write_json(evidence_dir / "RC4_PROMOTION_EVIDENCE_GATE.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="RC4 promotion-evidence outer gate successor")
    parser.add_argument("candidate_root", type=Path)
    parser.add_argument("evidence_dir", type=Path)
    args = parser.parse_args()
    try:
        report = gate(args.candidate_root, args.evidence_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCK", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
