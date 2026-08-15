"""Verify reviewed-risk attestations through a release-pinned signed root.

The release checkpoint is expected to live in the verified repository/release state.
Mutable Termux state may supply signed root metadata and attestations, but neither can
replace the independently pinned root fingerprint or minimum accepted root version.
RSA PKCS#1 v1.5 with SHA-256 is used without third-party dependencies.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX = re.compile(r"^[0-9a-fA-F]+$")
SHA256_DIGESTINFO_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")
MAX_FUTURE_SKEW = timedelta(minutes=5)


class VerificationError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid JSON file: {path}") from exc
    if not isinstance(value, dict):
        raise VerificationError(f"JSON object required: {path}")
    return value


def _parse_time(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise VerificationError(f"{field} must be a non-empty RFC3339 string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise VerificationError(f"invalid {field}") from exc
    if parsed.tzinfo is None:
        raise VerificationError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _canonical_attestation(attestation: dict[str, object]) -> bytes:
    signed_fields = {
        "schema": attestation.get("schema"),
        "authority_key_id": attestation.get("authority_key_id"),
        "verdict_id": attestation.get("verdict_id"),
        "verdict": attestation.get("verdict"),
        "verifier": attestation.get("verifier"),
        "artifact_sha256": attestation.get("artifact_sha256"),
        "findings_sha256": attestation.get("findings_sha256"),
        "issued_at": attestation.get("issued_at"),
        "expires_at": attestation.get("expires_at"),
    }
    return _canonical_json(signed_fields)


def _canonical_root_metadata(metadata: dict[str, object]) -> bytes:
    signed_fields = {
        "schema": metadata.get("schema"),
        "version": metadata.get("version"),
        "root_key": metadata.get("root_key"),
        "active_judge_keys": metadata.get("active_judge_keys"),
        "revoked_key_ids": metadata.get("revoked_key_ids"),
        "issued_at": metadata.get("issued_at"),
        "expires_at": metadata.get("expires_at"),
    }
    return _canonical_json(signed_fields)


def _parse_rsa_key(value: object, field: str) -> tuple[str, int, int]:
    if not isinstance(value, dict):
        raise VerificationError(f"{field} must be an object")
    key_id = value.get("key_id")
    n_hex = value.get("n_hex")
    exponent = value.get("e")
    if not isinstance(key_id, str) or not key_id:
        raise VerificationError(f"{field}.key_id missing")
    if not isinstance(n_hex, str) or not HEX.fullmatch(n_hex):
        raise VerificationError(f"{field}.n_hex invalid")
    if not isinstance(exponent, int):
        raise VerificationError(f"{field}.e invalid")
    modulus = int(n_hex, 16)
    if modulus <= 0 or exponent < 3 or exponent % 2 == 0:
        raise VerificationError(f"{field} contains invalid RSA parameters")
    return key_id, modulus, exponent


def _key_fingerprint(value: object, field: str) -> str:
    key_id, modulus, exponent = _parse_rsa_key(value, field)
    canonical = {
        "e": exponent,
        "key_id": key_id,
        "n_hex": format(modulus, "x"),
    }
    return hashlib.sha256(_canonical_json(canonical)).hexdigest()


def _decode_signature(value: object, field: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise VerificationError(f"{field} required")
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise VerificationError(f"{field} invalid") from exc


def _verify_rsa_pkcs1_v15_sha256(
    message: bytes, signature: bytes, *, modulus: int, exponent: int
) -> None:
    width = (modulus.bit_length() + 7) // 8
    if len(signature) != width:
        raise VerificationError("signature length does not match authority key")
    sig_int = int.from_bytes(signature, "big")
    if sig_int >= modulus:
        raise VerificationError("signature integer outside authority key range")
    encoded = pow(sig_int, exponent, modulus).to_bytes(width, "big")
    digest_info = SHA256_DIGESTINFO_PREFIX + hashlib.sha256(message).digest()
    padding_len = width - len(digest_info) - 3
    if padding_len < 8:
        raise VerificationError("authority key too small for SHA-256 signature")
    expected = b"\x00\x01" + (b"\xff" * padding_len) + b"\x00" + digest_info
    if encoded != expected:
        raise VerificationError("invalid signature")


def _verify_root_metadata(
    checkpoint: dict[str, object], metadata: dict[str, object], *, now: datetime
) -> tuple[int, dict[str, dict[str, object]], set[str], str]:
    if checkpoint.get("schema") != "centinal26-review-root-checkpoint-v1":
        raise VerificationError("unsupported review root checkpoint schema")
    if checkpoint.get("provisioned") is not True:
        raise VerificationError("review root checkpoint is not provisioned")
    pinned = checkpoint.get("root_key_fingerprint_sha256")
    if not isinstance(pinned, str) or not HEX64.fullmatch(pinned):
        raise VerificationError("checkpoint root fingerprint invalid")
    minimum = checkpoint.get("min_root_version")
    if not isinstance(minimum, int) or minimum < 1:
        raise VerificationError("checkpoint min_root_version invalid")

    if metadata.get("schema") != "centinal26-review-root-metadata-v1":
        raise VerificationError("unsupported review root metadata schema")
    version = metadata.get("version")
    if not isinstance(version, int) or version < minimum:
        raise VerificationError("review root metadata below release checkpoint")

    root_key = metadata.get("root_key")
    root_key_id, root_modulus, root_exponent = _parse_rsa_key(root_key, "root_key")
    fingerprint = _key_fingerprint(root_key, "root_key")
    if fingerprint != pinned:
        raise VerificationError("review root fingerprint does not match release checkpoint")

    issued_at = _parse_time(metadata.get("issued_at"), "root issued_at")
    expires_at = _parse_time(metadata.get("expires_at"), "root expires_at")
    if issued_at > now + MAX_FUTURE_SKEW:
        raise VerificationError("review root issued_at is in the future")
    if expires_at <= issued_at or expires_at <= now:
        raise VerificationError("review root metadata is stale or expired")

    signature = _decode_signature(metadata.get("signature_b64"), "root signature_b64")
    _verify_rsa_pkcs1_v15_sha256(
        _canonical_root_metadata(metadata),
        signature,
        modulus=root_modulus,
        exponent=root_exponent,
    )

    revoked_value = metadata.get("revoked_key_ids")
    if not isinstance(revoked_value, list) or not all(isinstance(item, str) for item in revoked_value):
        raise VerificationError("revoked_key_ids must be a string list")
    revoked = set(revoked_value)

    active_value = metadata.get("active_judge_keys")
    if not isinstance(active_value, list) or not active_value:
        raise VerificationError("active_judge_keys must be a non-empty list")
    active: dict[str, dict[str, object]] = {}
    for index, item in enumerate(active_value):
        if not isinstance(item, dict):
            raise VerificationError("active_judge_keys entries must be objects")
        key_id, _, _ = _parse_rsa_key(item, f"active_judge_keys[{index}]")
        if key_id in active:
            raise VerificationError("duplicate active Judge key_id")
        _parse_time(item.get("not_before"), f"active_judge_keys[{index}].not_before")
        _parse_time(item.get("not_after"), f"active_judge_keys[{index}].not_after")
        active[key_id] = item

    if root_key_id in revoked:
        raise VerificationError("pinned root key cannot be listed as revoked Judge key")
    return version, active, revoked, fingerprint


def verify(
    attestation_path: Path,
    root_metadata_path: Path,
    checkpoint_path: Path,
    artifact_sha256: str,
    findings_sha256: str,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    artifact_sha256 = artifact_sha256.lower()
    findings_sha256 = findings_sha256.lower()
    if not HEX64.fullmatch(artifact_sha256) or not HEX64.fullmatch(findings_sha256):
        raise VerificationError("artifact/findings identities must be lowercase SHA-256")

    checkpoint = _load_json(checkpoint_path)
    metadata = _load_json(root_metadata_path)
    attestation = _load_json(attestation_path)
    current = (now or datetime.now(UTC)).astimezone(UTC)

    root_version, active_keys, revoked, root_fingerprint = _verify_root_metadata(
        checkpoint, metadata, now=current
    )

    if attestation.get("schema") != "centinal26-reviewed-artifact-attestation-v1":
        raise VerificationError("unsupported review attestation schema")
    key_id = attestation.get("authority_key_id")
    if not isinstance(key_id, str) or not key_id:
        raise VerificationError("attestation authority_key_id missing")
    if key_id in revoked:
        raise VerificationError("attestation Judge key is revoked")
    judge_key = active_keys.get(key_id)
    if judge_key is None:
        raise VerificationError("attestation Judge key is not active in signed root metadata")

    if attestation.get("verdict") != "VERIFIED" or attestation.get("verifier") != "Frost Judge":
        raise VerificationError("attestation is not an independent Frost Judge VERIFIED verdict")
    verdict_id = attestation.get("verdict_id")
    if not isinstance(verdict_id, str) or not verdict_id.startswith("verdict:"):
        raise VerificationError("stable Judge verdict_id required")
    if attestation.get("artifact_sha256") != artifact_sha256:
        raise VerificationError("attestation artifact identity mismatch")
    if attestation.get("findings_sha256") != findings_sha256:
        raise VerificationError("attestation findings identity mismatch")

    issued_at = _parse_time(attestation.get("issued_at"), "issued_at")
    expires_at = _parse_time(attestation.get("expires_at"), "expires_at")
    if issued_at > current + MAX_FUTURE_SKEW:
        raise VerificationError("attestation issued_at is in the future")
    if expires_at <= issued_at or expires_at <= current:
        raise VerificationError("attestation is stale or expired")

    key_not_before = _parse_time(judge_key.get("not_before"), "Judge key not_before")
    key_not_after = _parse_time(judge_key.get("not_after"), "Judge key not_after")
    if key_not_after <= key_not_before:
        raise VerificationError("Judge key validity interval invalid")
    if issued_at < key_not_before or expires_at > key_not_after:
        raise VerificationError("attestation validity exceeds Judge key validity interval")

    _, judge_modulus, judge_exponent = _parse_rsa_key(judge_key, "Judge key")
    signature = _decode_signature(attestation.get("signature_b64"), "attestation signature_b64")
    _verify_rsa_pkcs1_v15_sha256(
        _canonical_attestation(attestation),
        signature,
        modulus=judge_modulus,
        exponent=judge_exponent,
    )
    return {
        "decision": "VERIFIED_ALLOW",
        "verdict_id": verdict_id,
        "artifact_sha256": artifact_sha256,
        "findings_sha256": findings_sha256,
        "authority_key_id": key_id,
        "root_version": root_version,
        "root_key_fingerprint_sha256": root_fingerprint,
        "root_metadata_sha256": hashlib.sha256(root_metadata_path.read_bytes()).hexdigest(),
        "attestation_sha256": hashlib.sha256(attestation_path.read_bytes()).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attestation", required=True, type=Path)
    parser.add_argument("--root-metadata", dest="root_metadata", type=Path)
    parser.add_argument("--authority", dest="legacy_root_metadata", type=Path)
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "security" / "review_root_checkpoint.json",
    )
    parser.add_argument("--artifact-sha256", required=True)
    parser.add_argument("--findings-sha256", required=True)
    args = parser.parse_args()
    root_metadata = args.root_metadata or args.legacy_root_metadata
    if root_metadata is None:
        parser.error("one of --root-metadata or --authority is required")
    try:
        result = verify(
            args.attestation,
            root_metadata,
            args.checkpoint,
            args.artifact_sha256,
            args.findings_sha256,
        )
    except VerificationError as exc:
        print(json.dumps({"decision": "DENY", "reason": str(exc)}, sort_keys=True))
        return 23
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
