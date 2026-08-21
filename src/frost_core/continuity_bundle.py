from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


class ContinuityBundleError(ValueError):
    """A portable continuity bundle failed structural or cryptographic verification."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _run_openssl(args: list[str]) -> None:
    try:
        completed = subprocess.run(
            ["openssl", *args],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise ContinuityBundleError("OpenSSL Ed25519 provider unavailable") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ContinuityBundleError(f"OpenSSL operation failed: {detail}")


def _write_zip_member(archive: zipfile.ZipFile, name: str, payload: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100600 << 16
    archive.writestr(info, payload)


def create_signed_bundle(
    proposal: dict[str, Any],
    output_path: str | Path,
    *,
    private_key: str | Path,
) -> dict[str, Any]:
    """Create a deterministic ZIP whose manifest is signed with an Ed25519 key.

    The public key is deliberately not embedded. Verification requires an independently
    selected public key so a bundle cannot define its own trust root.
    """

    proposal_bytes = _canonical_json(proposal)
    manifest = {
        "schema": "frost.continuity.portable_bundle.v1",
        "signature_algorithm": "Ed25519",
        "payload_member": "proposal.json",
        "payload_sha256": hashlib.sha256(proposal_bytes).hexdigest(),
    }
    manifest_bytes = _canonical_json(manifest)

    private = Path(private_key)
    if not private.is_file():
        raise ContinuityBundleError("private signing key does not exist")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="frost-continuity-sign-") as tmp:
        tmpdir = Path(tmp)
        manifest_file = tmpdir / "manifest.json"
        signature_file = tmpdir / "manifest.sig"
        manifest_file.write_bytes(manifest_bytes)
        _run_openssl(
            [
                "pkeyutl",
                "-sign",
                "-rawin",
                "-inkey",
                str(private),
                "-in",
                str(manifest_file),
                "-out",
                str(signature_file),
            ]
        )
        signature = signature_file.read_bytes()

    temporary = output.with_name(f".{output.name}.tmp")
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            _write_zip_member(archive, "manifest.json", manifest_bytes)
            _write_zip_member(archive, "proposal.json", proposal_bytes)
            _write_zip_member(archive, "manifest.sig", signature)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)

    return {
        "bundle_path": str(output),
        "bundle_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "payload_sha256": manifest["payload_sha256"],
        "signature_algorithm": "Ed25519",
    }


def verify_signed_bundle(
    bundle_path: str | Path,
    *,
    public_key: str | Path,
) -> dict[str, Any]:
    public = Path(public_key)
    if not public.is_file():
        raise ContinuityBundleError("public verification key does not exist")
    bundle = Path(bundle_path)
    if not bundle.is_file():
        raise ContinuityBundleError("bundle does not exist")

    try:
        with zipfile.ZipFile(bundle, "r") as archive:
            names = archive.namelist()
            required = ["manifest.json", "proposal.json", "manifest.sig"]
            if len(names) != len(set(names)) or sorted(names) != sorted(required):
                raise ContinuityBundleError("bundle member set is not canonical")
            manifest_bytes = archive.read("manifest.json")
            proposal_bytes = archive.read("proposal.json")
            signature = archive.read("manifest.sig")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ContinuityBundleError("invalid continuity ZIP") from exc

    try:
        manifest = json.loads(manifest_bytes)
        proposal = json.loads(proposal_bytes)
    except json.JSONDecodeError as exc:
        raise ContinuityBundleError("bundle JSON is invalid") from exc
    if _canonical_json(manifest) != manifest_bytes or _canonical_json(proposal) != proposal_bytes:
        raise ContinuityBundleError("bundle JSON is not canonical")
    if manifest.get("schema") != "frost.continuity.portable_bundle.v1":
        raise ContinuityBundleError("unsupported portable bundle schema")
    if manifest.get("signature_algorithm") != "Ed25519":
        raise ContinuityBundleError("unsupported signature algorithm")
    actual_payload = hashlib.sha256(proposal_bytes).hexdigest()
    if manifest.get("payload_sha256") != actual_payload:
        raise ContinuityBundleError("proposal SHA-256 mismatch")

    with tempfile.TemporaryDirectory(prefix="frost-continuity-verify-") as tmp:
        tmpdir = Path(tmp)
        manifest_file = tmpdir / "manifest.json"
        signature_file = tmpdir / "manifest.sig"
        manifest_file.write_bytes(manifest_bytes)
        signature_file.write_bytes(signature)
        _run_openssl(
            [
                "pkeyutl",
                "-verify",
                "-rawin",
                "-pubin",
                "-inkey",
                str(public),
                "-in",
                str(manifest_file),
                "-sigfile",
                str(signature_file),
            ]
        )

    return {
        "status": "VERIFIED",
        "bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
        "payload_sha256": actual_payload,
        "proposal": proposal,
    }
