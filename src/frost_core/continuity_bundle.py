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


_MAX_MANIFEST_BYTES = 64 * 1024
_MAX_PROPOSAL_BYTES = 64 * 1024 * 1024
_MAX_SIGNATURE_BYTES = 1024
_ED25519_SIGNATURE_BYTES = 64


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _regular_file(path: Path, *, label: str) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ContinuityBundleError(f"{label} must be a regular non-symlink file")
    return path


def _run_openssl(args: list[str]) -> None:
    try:
        completed = subprocess.run(
            ["openssl", *args],
            check=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
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


def _read_bounded_member(archive: zipfile.ZipFile, name: str, *, limit: int) -> bytes:
    try:
        info = archive.getinfo(name)
    except KeyError as exc:
        raise ContinuityBundleError(f"missing bundle member: {name}") from exc
    if info.is_dir() or info.flag_bits & 0x1:
        raise ContinuityBundleError(f"unsupported ZIP member flags: {name}")
    if info.file_size < 0 or info.file_size > limit:
        raise ContinuityBundleError(f"bundle member exceeds size limit: {name}")
    payload = archive.read(info)
    if len(payload) != info.file_size:
        raise ContinuityBundleError(f"bundle member size mismatch: {name}")
    return payload


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
    if len(proposal_bytes) > _MAX_PROPOSAL_BYTES:
        raise ContinuityBundleError("proposal exceeds portable bundle size limit")
    manifest = {
        "schema": "frost.continuity.portable_bundle.v1",
        "signature_algorithm": "Ed25519",
        "payload_member": "proposal.json",
        "payload_sha256": hashlib.sha256(proposal_bytes).hexdigest(),
    }
    manifest_bytes = _canonical_json(manifest)

    private = _regular_file(Path(private_key), label="private signing key")
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
    if len(signature) != _ED25519_SIGNATURE_BYTES:
        raise ContinuityBundleError("OpenSSL returned an invalid Ed25519 signature length")

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
        "bundle_sha256": _sha256_file(output),
        "payload_sha256": manifest["payload_sha256"],
        "signature_algorithm": "Ed25519",
    }


def verify_signed_bundle(
    bundle_path: str | Path,
    *,
    public_key: str | Path,
) -> dict[str, Any]:
    public = _regular_file(Path(public_key), label="public verification key")
    bundle = _regular_file(Path(bundle_path), label="bundle")

    try:
        with zipfile.ZipFile(bundle, "r") as archive:
            names = archive.namelist()
            required = ["manifest.json", "proposal.json", "manifest.sig"]
            if len(names) != len(set(names)) or sorted(names) != sorted(required):
                raise ContinuityBundleError("bundle member set is not canonical")
            manifest_bytes = _read_bounded_member(
                archive, "manifest.json", limit=_MAX_MANIFEST_BYTES
            )
            proposal_bytes = _read_bounded_member(
                archive, "proposal.json", limit=_MAX_PROPOSAL_BYTES
            )
            signature = _read_bounded_member(
                archive, "manifest.sig", limit=_MAX_SIGNATURE_BYTES
            )
    except zipfile.BadZipFile as exc:
        raise ContinuityBundleError("invalid continuity ZIP") from exc

    if len(signature) != _ED25519_SIGNATURE_BYTES:
        raise ContinuityBundleError("invalid Ed25519 signature length")
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
    if manifest.get("payload_member") != "proposal.json":
        raise ContinuityBundleError("unsupported payload member")
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
        "bundle_sha256": _sha256_file(bundle),
        "payload_sha256": actual_payload,
        "proposal": proposal,
    }
