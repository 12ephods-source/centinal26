from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_review_attestation", ROOT / "scripts" / "verify_review_attestation.py"
)
assert SPEC and SPEC.loader
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)

TEST_RSA_N = int(
    "c6acbcbac4956409542783048cc8f924c6c29a0b2c134d048be57828429071cbe348a12cf84287721d3b1e418be09018758638397e581826d3cbeabba7dd2ab6985ed1ab58facc658c9a18ef036402e84f5006a88f0054a99a231a073fbe9038210d23c87c51c8a1c954f1c46ac9f2c111864473c27a8d20dc8ddf88dd6143916c61e41ac1f032adcef0555b7a549671a4f1c85e311d262138013f24fba93e64497b2708d3fd2f690c2c7937d4834e466568e4db4b214046f584a21c24d50a6e8207d35b047a0f785fb1ae7c7c68283c8edd3ddd9e378908a56993a15034cdf81bd8130776920ec20671bbf46af2fa8be21be14ec0366795a2c1d02f8e5285b5",
    16,
)
TEST_RSA_D = int(
    "2c53c39b1f3bdeb14725b6b187f0da47c6920a3926691b04c1eaddb38be07b075ceb6a4ca48a817a6843b5b535ae91afe75ede4213aab79ec82025fc1f10b5543eac5f370e180d0d3640f681b37db7b959e2d6cd7a747e2f462d01446f484718c2e511e00c3eda1720dad34379f91b70d0c66694f6660e01703c364cece9e3df54070f05eac37f5af549413f9c3ee611d1db77e37f2d5c6bfa43f1991f94e4461fb913040442884619a27941c013899b9ac37b4a7fc7376aa5600497a08d701fddd7e2323742f18c779c902b063e1d0ef1717434b87f79560ac7741a515ed3b4283e5d1285f5eae8b2d42d52988d90ceda85b9b0da7e6ca0ac7ee29157463b51",
    16,
)
DIGESTINFO_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


def _sign(message: bytes) -> str:
    digest_info = DIGESTINFO_PREFIX + hashlib.sha256(message).digest()
    width = (TEST_RSA_N.bit_length() + 7) // 8
    encoded = b"\x00\x01" + b"\xff" * (width - len(digest_info) - 3) + b"\x00" + digest_info
    signature = pow(int.from_bytes(encoded, "big"), TEST_RSA_D, TEST_RSA_N).to_bytes(width, "big")
    return base64.b64encode(signature).decode()


def _key(key_id: str) -> dict[str, object]:
    return {"key_id": key_id, "n_hex": format(TEST_RSA_N, "x"), "e": 65537}


def _write_chain(
    tmp_path: Path,
    *,
    version: int = 1,
    min_version: int = 1,
    provisioned: bool = True,
    revoked: list[str] | None = None,
    wrong_fingerprint: bool = False,
) -> tuple[Path, Path, Path]:
    now = datetime.now(UTC)
    root_key = _key("test-root-v1")
    judge_key = {
        **_key("test-judge-v1"),
        "not_before": (now - timedelta(hours=1)).isoformat(),
        "not_after": (now + timedelta(hours=2)).isoformat(),
    }
    metadata: dict[str, object] = {
        "schema": "centinal26-review-root-metadata-v1",
        "version": version,
        "root_key": root_key,
        "active_judge_keys": [judge_key],
        "revoked_key_ids": revoked or [],
        "issued_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
    }
    metadata["signature_b64"] = _sign(VERIFIER._canonical_root_metadata(metadata))
    fingerprint = VERIFIER._key_fingerprint(root_key, "root_key")
    if wrong_fingerprint:
        fingerprint = "f" * 64
    checkpoint = {
        "schema": "centinal26-review-root-checkpoint-v1",
        "release": "1.0.0",
        "provisioned": provisioned,
        "min_root_version": min_version,
        "root_key_fingerprint_sha256": fingerprint,
    }
    attestation: dict[str, object] = {
        "schema": "centinal26-reviewed-artifact-attestation-v1",
        "authority_key_id": "test-judge-v1",
        "verdict_id": "verdict:test-root-chain-v1",
        "verdict": "VERIFIED",
        "verifier": "Frost Judge",
        "artifact_sha256": "a" * 64,
        "findings_sha256": "b" * 64,
        "issued_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(minutes=30)).isoformat(),
    }
    attestation["signature_b64"] = _sign(VERIFIER._canonical_attestation(attestation))

    paths = []
    for name, payload in (
        ("checkpoint.json", checkpoint),
        ("root.json", metadata),
        ("attestation.json", attestation),
    ):
        path = tmp_path / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths.append(path)
    return paths[0], paths[1], paths[2]


def _verify(checkpoint: Path, root: Path, attestation: Path):
    return VERIFIER.verify(attestation, root, checkpoint, "a" * 64, "b" * 64)


def test_signed_root_chain_allows_active_judge_key(tmp_path: Path):
    checkpoint, root, attestation = _write_chain(tmp_path)
    result = _verify(checkpoint, root, attestation)
    assert result["decision"] == "VERIFIED_ALLOW"
    assert result["root_version"] == 1
    assert result["authority_key_id"] == "test-judge-v1"


def test_release_checkpoint_blocks_rollback(tmp_path: Path):
    checkpoint, root, attestation = _write_chain(tmp_path, version=1, min_version=2)
    try:
        _verify(checkpoint, root, attestation)
    except VERIFIER.VerificationError as exc:
        assert "below release checkpoint" in str(exc)
    else:
        raise AssertionError("root rollback was accepted")


def test_unprovisioned_or_wrong_root_fingerprint_fails_closed(tmp_path: Path):
    checkpoint, root, attestation = _write_chain(tmp_path, provisioned=False)
    try:
        _verify(checkpoint, root, attestation)
    except VERIFIER.VerificationError as exc:
        assert "not provisioned" in str(exc)
    else:
        raise AssertionError("unprovisioned checkpoint was accepted")

    checkpoint, root, attestation = _write_chain(tmp_path, wrong_fingerprint=True)
    try:
        _verify(checkpoint, root, attestation)
    except VERIFIER.VerificationError as exc:
        assert "does not match release checkpoint" in str(exc)
    else:
        raise AssertionError("wrong root fingerprint was accepted")


def test_revoked_judge_key_fails_closed(tmp_path: Path):
    checkpoint, root, attestation = _write_chain(tmp_path, revoked=["test-judge-v1"])
    try:
        _verify(checkpoint, root, attestation)
    except VERIFIER.VerificationError as exc:
        assert "revoked" in str(exc)
    else:
        raise AssertionError("revoked Judge key was accepted")


def test_committed_release_checkpoint_is_fail_closed_until_real_root_is_provisioned():
    checkpoint = json.loads((ROOT / "security" / "review_root_checkpoint.json").read_text())
    assert checkpoint["schema"] == "centinal26-review-root-checkpoint-v1"
    assert checkpoint["provisioned"] is False
    assert checkpoint["root_key_fingerprint_sha256"] == "0" * 64
