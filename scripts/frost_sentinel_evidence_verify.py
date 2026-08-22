from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

HEX64 = re.compile(r"^[0-9a-f]{64}$")
CLAIM_SCOPE_BY_RUNTIME = {
    "HOST_OR_SESSION": "SOFTWARE_ONLY",
    "ANDROID_FIXTURE": "ANDROID_LOGIC_AND_SOFTWARE",
    "ANDROID_TERMUX": "DEVICE_ORIGIN_AND_SOFTWARE",
}
ZERO_HASH = "0" * 64


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _manifest_entries(run_dir: Path) -> tuple[list[tuple[str, str]], list[str]]:
    errors: list[str] = []
    manifest = run_dir / "SHA256SUMS.txt"
    if not manifest.is_file():
        return [], [f"{run_dir.name}:missing_manifest"]

    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for number, raw in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        parts = raw.split(maxsplit=1)
        if len(parts) != 2:
            errors.append(f"{run_dir.name}:manifest_line_{number}:malformed")
            continue
        expected, relative = parts
        relative = relative.lstrip("*")
        if not HEX64.fullmatch(expected):
            errors.append(f"{run_dir.name}:manifest_line_{number}:invalid_hash")
            continue
        rel_path = Path(relative)
        if rel_path.is_absolute() or ".." in rel_path.parts:
            errors.append(f"{run_dir.name}:manifest_line_{number}:unsafe_path")
            continue
        normalized = relative.removeprefix("./")
        if normalized in seen:
            errors.append(f"{run_dir.name}:manifest_line_{number}:duplicate_path")
            continue
        seen.add(normalized)
        entries.append((expected, normalized))
    if not entries:
        errors.append(f"{run_dir.name}:empty_manifest")
    return entries, errors


def _verify_archive(
    archive: Path,
    run_id: str,
    manifest_hash: str,
    entries: list[tuple[str, str]],
) -> list[str]:
    errors: list[str] = []
    try:
        with tarfile.open(archive, "r:gz") as bundle:
            members = {member.name: member for member in bundle.getmembers()}
            archived_manifest = members.get(f"{run_id}/SHA256SUMS.txt")
            if archived_manifest is None:
                errors.append(f"{run_id}:archive_missing_manifest")
            else:
                extracted = bundle.extractfile(archived_manifest)
                if extracted is None or _sha256_bytes(extracted.read()) != manifest_hash:
                    errors.append(f"{run_id}:archive_manifest_hash_mismatch")

            for expected, relative in entries:
                name = f"{run_id}/{relative}"
                member = members.get(name)
                if member is None or not member.isfile():
                    errors.append(f"{run_id}:archive_missing:{relative}")
                    continue
                extracted = bundle.extractfile(member)
                if extracted is None or _sha256_bytes(extracted.read()) != expected:
                    errors.append(f"{run_id}:archive_hash_mismatch:{relative}")
    except (tarfile.TarError, OSError) as exc:
        errors.append(f"{run_id}:archive_unreadable:{type(exc).__name__}")
    return errors


def _verify_run(
    base: Path,
    fields: list[str],
) -> tuple[dict[str, Any] | None, list[str]]:
    _, ledger_time, case_id, operator, run_id, manifest_hash, archive_hash, _ = fields
    errors: list[str] = []
    if not HEX64.fullmatch(manifest_hash):
        errors.append(f"{run_id}:ledger_manifest_hash_invalid")
    if not HEX64.fullmatch(archive_hash):
        errors.append(f"{run_id}:ledger_archive_hash_invalid")

    run_dir = base / "runs" / run_id
    if not run_dir.is_dir():
        return None, errors + [f"{run_id}:missing_run_directory"]

    entries, manifest_errors = _manifest_entries(run_dir)
    errors.extend(manifest_errors)
    manifest = run_dir / "SHA256SUMS.txt"
    if manifest.is_file() and _sha256_file(manifest) != manifest_hash:
        errors.append(f"{run_id}:manifest_digest_mismatch")

    for expected, relative in entries:
        path = run_dir / relative
        if not path.is_file():
            errors.append(f"{run_id}:missing_file:{relative}")
            continue
        if _sha256_file(path) != expected:
            errors.append(f"{run_id}:file_hash_mismatch:{relative}")

    archive = base / f"{run_id}.tar.gz"
    if not archive.is_file():
        errors.append(f"{run_id}:missing_archive")
    else:
        if _sha256_file(archive) != archive_hash:
            errors.append(f"{run_id}:archive_digest_mismatch")
        errors.extend(_verify_archive(archive, run_id, manifest_hash, entries))

    sidecar = base / f"{run_id}.tar.gz.sha256"
    if not sidecar.is_file():
        errors.append(f"{run_id}:missing_archive_sidecar")
    else:
        token = sidecar.read_text(encoding="utf-8").split(maxsplit=1)[0].lower()
        if token != archive_hash:
            errors.append(f"{run_id}:archive_sidecar_mismatch")

    meta = run_dir / "meta"
    required_meta = {
        "execution_id": meta / "execution_id.txt",
        "acquisition_started_utc": meta / "acquisition_started_utc.txt",
        "acquisition_finished_utc": meta / "acquisition_finished_utc.txt",
        "case_id": meta / "case_id.txt",
        "operator": meta / "operator.txt",
        "runtime_class": meta / "runtime_class.txt",
        "claim_scope": meta / "claim_scope.txt",
    }
    values: dict[str, str] = {}
    for key, path in required_meta.items():
        if not path.is_file():
            errors.append(f"{run_id}:missing_meta:{key}")
        else:
            values[key] = _read_text(path)

    if values.get("execution_id") != run_id:
        errors.append(f"{run_id}:execution_id_mismatch")
    if values.get("case_id") != case_id:
        errors.append(f"{run_id}:case_id_mismatch")
    if values.get("operator") != operator:
        errors.append(f"{run_id}:operator_mismatch")

    runtime_class = values.get("runtime_class", "")
    claim_scope = values.get("claim_scope", "")
    expected_scope = CLAIM_SCOPE_BY_RUNTIME.get(runtime_class)
    if expected_scope is None:
        errors.append(f"{run_id}:unknown_runtime_class:{runtime_class}")
    elif claim_scope != expected_scope:
        errors.append(f"{run_id}:claim_scope_mismatch")

    started = values.get("acquisition_started_utc", "")
    finished = values.get("acquisition_finished_utc", "")
    try:
        started_dt = _parse_utc(started)
        finished_dt = _parse_utc(finished)
        ledger_dt = _parse_utc(ledger_time)
    except ValueError:
        errors.append(f"{run_id}:invalid_timestamp")
    else:
        if started_dt > finished_dt:
            errors.append(f"{run_id}:acquisition_time_reversed")
        if ledger_dt < finished_dt:
            errors.append(f"{run_id}:ledger_precedes_acquisition_finish")

    timeline = {
        "run_id": run_id,
        "case_id": case_id,
        "operator": operator,
        "acquisition_started_utc": started,
        "acquisition_finished_utc": finished,
        "custody_recorded_utc": ledger_time,
        "runtime_class": runtime_class,
        "claim_scope": claim_scope,
        "manifest_sha256": manifest_hash,
        "archive_sha256": archive_hash,
        "device_origin_metadata_present": runtime_class == "ANDROID_TERMUX",
        "device_origin_independently_corroborated": False,
    }
    return timeline, errors


def verify_base(base: Path, require_runs: int = 1) -> dict[str, Any]:
    base = base.resolve()
    errors: list[str] = []
    ledger = base / "custody_chain.tsv"
    timeline: list[dict[str, Any]] = []
    if not ledger.is_file():
        errors.append("missing_custody_ledger")
        lines: list[str] = []
    else:
        lines = [line for line in ledger.read_text(encoding="utf-8").splitlines() if line]

    previous = ZERO_HASH
    seen_runs: set[str] = set()
    for number, line in enumerate(lines, 1):
        fields = line.split("\t")
        if len(fields) != 8:
            errors.append(f"ledger_line_{number}:field_count")
            continue
        record_hash = fields[0]
        if not HEX64.fullmatch(record_hash):
            errors.append(f"ledger_line_{number}:record_hash_invalid")
        calculated = _sha256_bytes("\t".join(fields[1:]).encode("utf-8"))
        if calculated != record_hash:
            errors.append(f"ledger_line_{number}:record_hash_mismatch")
        if fields[7] != previous:
            errors.append(f"ledger_line_{number}:previous_hash_mismatch")
        previous = record_hash

        run_id = fields[4]
        if run_id in seen_runs:
            errors.append(f"ledger_line_{number}:duplicate_run_id")
            continue
        seen_runs.add(run_id)
        row, run_errors = _verify_run(base, fields)
        errors.extend(run_errors)
        if row is not None:
            timeline.append(row)

    if len(lines) < require_runs:
        errors.append(f"insufficient_runs:{len(lines)}<{require_runs}")

    timeline.sort(key=lambda row: (row["acquisition_started_utc"], row["run_id"]))
    for earlier, later in pairwise(timeline):
        if earlier["acquisition_started_utc"] > later["acquisition_started_utc"]:
            errors.append("timeline_ordering_failure")
            break

    passed = not errors
    return {
        "schema": "frost.sentinel.independent_evidence_verification/v1",
        "verdict": (
            "PASS_ARTIFACT_INTEGRITY_PROVENANCE_AND_ACQUISITION_TIMELINE"
            if passed
            else "FAIL_EVIDENCE_VERIFICATION"
        ),
        "pass": passed,
        "run_count": len(lines),
        "independent_integrity_corroboration": passed,
        "device_origin_independently_corroborated": False,
        "forensic_attribution_established": False,
        "scientific_or_empirical_truth_established": False,
        "errors": sorted(errors),
        "acquisition_timeline": timeline,
        "scope_note": (
            "This verifier independently recomputes artifact hashes, archive contents, "
            "custody-chain continuity, metadata consistency, claim-scope mapping and "
            "acquisition chronology. It does not independently prove that self-recorded "
            "ANDROID_TERMUX metadata originated on a specific handset and does not "
            "establish forensic attribution or semantic truth."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--require-runs", type=int, default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.require_runs < 0:
        parser.error("--require-runs must be non-negative")
    result = verify_base(args.base, args.require_runs)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
