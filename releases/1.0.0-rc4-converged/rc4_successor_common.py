from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import tarfile
from pathlib import Path
from typing import Any

TARGET_RELEASE = "1.0.0-rc4-converged"
TARGET_SCHEMA = 10
SCHEMA10_INSTALLER_SHA256 = "e21ed868d11ec7525a0fba54e58854b00a9fd151681a1efc26ffd9cf202f40d2"
GA_INSTALLER_SHA256 = "cfd2e3e285550b2d4f995a7edf10377ca983276da9b79e16084e0a36b040e7d7"
SCHEMA10_PAYLOAD_SHA256 = "79e53364ff0462dadf9b1d454123791c0db26d0a860bda98cf3e788183106e0a"
GA_PAYLOAD_SHA256 = "692c59e891d5f539933c363563b1256b10c225d15878598724b9b6cca03c8f58"
ZERO_HASH = "0" * 64


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def tree_inventory(root: Path, *, exclude: set[str] | None = None) -> dict[str, dict[str, Any]]:
    excluded = exclude or set()
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if rel in excluded:
            continue
        result[rel] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
    return result


def tree_digest(root: Path, *, exclude: set[str] | None = None) -> str:
    inventory = tree_inventory(root, exclude=exclude)
    return sha256_bytes(canonical_json(inventory))


def extract_payload_b64(installer: Path) -> bytes:
    text = installer.read_text(encoding="utf-8", errors="strict")
    match = re.search(
        r"(?ms)^[^\n]*<<['\"]?PAYLOAD_B64['\"]?\s*$\n(?P<payload>.*?)^PAYLOAD_B64\s*$",
        text,
    )
    if not match:
        raise ValueError("PAYLOAD_B64 heredoc not found")
    compact = "".join(match.group("payload").split())
    return base64.b64decode(compact, validate=True)


def safe_extract_tar_gz(payload: bytes, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    dest_resolved = destination.resolve()
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        for member in archive.getmembers():
            if member.issym() or member.islnk() or member.isdev():
                raise ValueError(f"unsafe tar member type: {member.name}")
            target = (destination / member.name).resolve()
            if target != dest_resolved and dest_resolved not in target.parents:
                raise ValueError(f"tar path escapes destination: {member.name}")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise ValueError(f"unsupported tar member type: {member.name}")
            source = archive.extractfile(member)
            if source is None:
                raise ValueError(f"could not read tar member: {member.name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as out:
                while chunk := source.read(1024 * 1024):
                    out.write(chunk)


def verify_embedded_manifest(root: Path) -> dict[str, Any]:
    manifest_path = root / "MANIFEST.json"
    if not manifest_path.is_file():
        raise ValueError("embedded payload MANIFEST.json missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files")
    if not isinstance(files, list):
        raise ValueError("embedded MANIFEST.json has no files list")
    errors: list[str] = []
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            errors.append("invalid manifest item")
            continue
        path = root / item["path"]
        if not path.is_file():
            errors.append(f"missing: {item['path']}")
            continue
        expected_hash = item.get("sha256")
        expected_size = item.get("size_bytes")
        if expected_hash and sha256_file(path) != expected_hash:
            errors.append(f"sha256 mismatch: {item['path']}")
        if expected_size is not None and path.stat().st_size != int(expected_size):
            errors.append(f"size mismatch: {item['path']}")
    if errors:
        raise ValueError("; ".join(errors))
    return manifest


def verify_parent_installer(
    installer: Path,
    expected_installer_sha256: str,
    expected_payload_sha256: str,
    destination: Path,
) -> dict[str, Any]:
    if not installer.is_file():
        raise FileNotFoundError(installer)
    actual_installer = sha256_file(installer)
    if actual_installer != expected_installer_sha256:
        raise ValueError(
            f"installer SHA-256 mismatch: expected {expected_installer_sha256}, got {actual_installer}"
        )
    payload = extract_payload_b64(installer)
    actual_payload = sha256_bytes(payload)
    if actual_payload != expected_payload_sha256:
        raise ValueError(
            f"payload SHA-256 mismatch: expected {expected_payload_sha256}, got {actual_payload}"
        )
    safe_extract_tar_gz(payload, destination)
    manifest = verify_embedded_manifest(destination)
    return {
        "installer_path": str(installer.resolve()),
        "installer_sha256": actual_installer,
        "payload_sha256": actual_payload,
        "manifest_sha256": sha256_file(destination / "MANIFEST.json"),
        "manifest": manifest,
    }


def candidate_manifest(root: Path) -> dict[str, Any]:
    path = root / "MANIFEST.json"
    if not path.is_file():
        raise ValueError("candidate MANIFEST.json missing")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != "automation-rc4-successor-candidate-manifest-v1":
        raise ValueError("unexpected candidate manifest format")
    if data.get("release") != TARGET_RELEASE or data.get("schema_version") != TARGET_SCHEMA:
        raise ValueError("candidate release/schema mismatch")
    files = data.get("files")
    if not isinstance(files, list):
        raise ValueError("candidate manifest files list missing")
    errors: list[str] = []
    for item in files:
        path = root / str(item.get("path", ""))
        if not path.is_file():
            errors.append(f"missing: {item.get('path')}")
            continue
        if sha256_file(path) != item.get("sha256"):
            errors.append(f"sha256 mismatch: {item.get('path')}")
        if path.stat().st_size != int(item.get("size_bytes", -1)):
            errors.append(f"size mismatch: {item.get('path')}")
    if errors:
        raise ValueError("; ".join(errors))
    return data


def candidate_digest(root: Path) -> str:
    candidate_manifest(root)
    return tree_digest(root, exclude={"MANIFEST.json", "reports/RC4_HOST_QUALIFICATION.json"})
