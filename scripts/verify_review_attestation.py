#!/usr/bin/env python3
"""Verify a signed reviewed-risk attestation without third-party dependencies.

The authority file is trusted local state provisioned outside the repository review registry.
The attestation signature uses RSA PKCS#1 v1.5 with SHA-256 over canonical JSON.
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
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise VerificationError(f"invalid {field}") from exc
    if parsed.tzinfo is None:
        raise VerificationError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def _canonical_payload(attestation: dict[str, object]) -> bytes:
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
    return json.dumps(signed_fields, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _verify_rsa_pkcs1_v15_sha256(
    message: bytes, signature: bytes, *, modulus: int, exponent: int
) -> None:
    if modulus <= 0 or exponent < 3 or exponent % 2 == 0:
        raise VerificationError("invalid RSA authority key")
    width = (modulus.bit_length() + 7) // 8
    if len(signature) != width:
        raise VerificationError("signature length does not match authority key")
    sig_int = int.from_bytes(signature, "big")
    if sig_int >= modulus:
        raise VerificationError("signature integer outside authority key range")
    encoded = pow(sig_int, exponent, modulus).to_bytes(width, "big")
    digest = hashlib.sha256(message).digest()
    digest_info = SHA256_DIGESTINFO_PREFIX + digest
    padding_len = width - len(digest_info) - 3
    if padding_len < 8:
        raise VerificationError("authority key too small for SHA-256 signature")
    expected = b"\x00\x01" + (b"\xff" * padding_len) + b"\x00" + digest_info
    if encoded != expected:
        raise VerificationError("invalid attestation signature")


def verify(
    attestation_path: Path,
    authority_path: Path,
    artifact_sha256: str,
    findings_sha256: str,
    *,
    now: datetime | None = None,
) -> dict[str, str]:
    artifact_sha256 = artifact_sha256.lower()
    findings_sha256 = findings_sha256.lower()
    if not HEX64.fullmatch(artifact_sha256) or not HEX64.fullmatch(findings_sha256):
        raise VerificationError("artifact/findings identities must be lowercase SHA-256")

    authority = _load_json(authority_path)
    attestation = _load_json(attestation_path)
    if authority.get("schema") != "centinal26-review-authority-rsa-v1":
        raise VerificationError("unsupported review authority schema")
    if attestation.get("schema") != "centinal26-reviewed-artifact-attestation-v1":
        raise VerificationError("unsupported review attestation schema")

    key_id = authority.get("key_id")
    if not isinstance(key_id, str) or not key_id:
        raise VerificationError("authority key_id missing")
    if attestation.get("authority_key_id") != key_id:
        raise VerificationError("attestation authority key mismatch")
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
    current = (now or datetime.now(UTC)).astimezone(UTC)
    if issued_at > current + MAX_FUTURE_SKEW:
        raise VerificationError("attestation issued_at is in the future")
    if expires_at <= issued_at or expires_at <= current:
        raise VerificationError("attestation is stale or expired")

    n_hex = authority.get("n_hex")
    exponent = authority.get("e")
    if not isinstance(n_hex, str) or not re.fullmatch(r"[0-9a-fA-F]+", n_hex):
        raise VerificationError("authority n_hex invalid")
    if not isinstance(exponent, int):
        raise VerificationError("authority exponent invalid")
    signature_text = attestation.get("signature_b64")
    if not isinstance(signature_text, str) or not signature_text:
        raise VerificationError("signed attestation required")
    try:
        signature = base64.b64decode(signature_text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise VerificationError("signature_b64 invalid") from exc

    _verify_rsa_pkcs1_v15_sha256(
        _canonical_payload(attestation),
        signature,
        modulus=int(n_hex, 16),
        exponent=exponent,
    )
    return {
        "decision": "VERIFIED_ALLOW",
        "verdict_id": verdict_id,
        "artifact_sha256": artifact_sha256,
        "findings_sha256": findings_sha256,
        "authority_key_id": key_id,
        "attestation_sha256": hashlib.sha256(attestation_path.read_bytes()).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attestation", required=True, type=Path)
    parser.add_argument("--authority", required=True, type=Path)
    parser.add_argument("--artifact-sha256", required=True)
    parser.add_argument("--findings-sha256", required=True)
    args = parser.parse_args()
    try:
        result = verify(
            args.attestation,
            args.authority,
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
