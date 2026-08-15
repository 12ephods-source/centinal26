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
    "8bd3f84aff58ebad7a97228fb12318607aa13d387f6138601cc8b6313a661feaabe15f74ad6f884607034db418d527515e25664f4daf086659c76d3036e1bcf414810d17919684b3540c40d3a5f518b701f12f0c44f4791a773cb16df0f6cd211b52347a46aa00ab55ad0c63479795c5103dddb87dc9852e58cecca0930fee3fb140a460d3c915a584b4811a549eca2fcf7c859e90ede95b25bb2e8fe40396d4850ba6bb39800a2ebeb50ffa01bc0357fc971b1dacec717797208e4527974c16fd7b09cfc3886398a898d34b687e43f517e8c52e85718b56cb144cfd7f72e4f4e0553315fce314c858ee0549d435dde0205fbdceb6bae299963144a4bd65ee28b8389a651e4c183f31d01263db7f5188b06ca84b24d17d307058d36dbab0d7f10c2e8dcb4a153aff1732077104789420eeee901c47d7c1e9fe898fcd50ee6497756abd11e108e0017e7e805e2baef2b54dcd5509534ba8d1b2d617100315802b854b05ed852300d02e0c2db0e02718d1369258db3025d1dc1610895a3722d553",
    16,
)
TEST_RSA_D = int(
    "d846ad2d9377fe50fde4f6d83aac85eff4bda0ebda5a8dd05bb537d93cf2e93b1950274d5955c1fa4eae9569935f5ec9444da4c9d4e67e9f910e1d9d0dc66b753ca1bf964ce1fbaf44b90f2c4eeda3a4ada457992aaed9024e9bd9f4ab59923f3afb13a06ddc55dcad505470db3363bcc33a6dd006ffc4b7c3355adca39b686fabc2c87ddc16931cc8fe4912690092cb10ab1222091974703f141f19011d6c169b134279249f1f20de6940a4fa39cd1232e7a651683eefe2822720e7662d66c97f39f6bda99f0cda32049ed0424c3ec15e52ba77ec71892cef9ecfc8c6db45e531b1a3aa0bce97b67efdc042fc8d0673aa4e0a6e74d54996a4adf9c417c9c7acab9c4a1e3ab04b9ab1e65e6365ed8d240909e438f1261f113397f60792b831f831912d8acd3ec66869ea8fafa9fe0f50f8becb55fb58e5bd04dff6c13b3b06d9d3d80d4ae857499b848f0966bbc6f1c1da6d4627f5a69510e2d40d4ca72cab1d0c5a48e974aa709e9bc401a059384767abc9943395000e1a0f4ff70e94d489d",
    16,
)
DIGESTINFO_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")
PROFILE = {
    "schema": "centinal26-rsa-verification-profile-v1",
    "version": 1,
    "min_rsa_bits": 3072,
    "required_exponent": 65537,
}


def _sign(message: bytes) -> str:
    digest_info = DIGESTINFO_PREFIX + hashlib.sha256(message).digest()
    width = (TEST_RSA_N.bit_length() + 7) // 8
    encoded = b"\x00\x01" + b"\xff" * (width - len(digest_info) - 3) + b"\x00" + digest_info
    signature = pow(int.from_bytes(encoded, "big"), TEST_RSA_D, TEST_RSA_N).to_bytes(width, "big")
    return base64.b64encode(signature).decode()


def _key(key_id: str, *, exponent: int = 65537) -> dict[str, object]:
    return {"key_id": key_id, "n_hex": format(TEST_RSA_N, "x"), "e": exponent}


def _write_chain(
    tmp_path: Path,
    *,
    version: int = 1,
    min_version: int = 1,
    provisioned: bool = True,
    revoked: list[str] | None = None,
    wrong_fingerprint: bool = False,
    profile: dict[str, object] | None = None,
) -> tuple[Path, Path, Path]:
    now = datetime.now(UTC)
    selected_profile = dict(profile or PROFILE)
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
    fingerprint = VERIFIER._key_fingerprint(root_key, "root_key", selected_profile)
    if wrong_fingerprint:
        fingerprint = "f" * 64
    checkpoint = {
        "schema": "centinal26-review-root-checkpoint-v1",
        "release": "1.0.0",
        "provisioned": provisioned,
        "min_root_version": min_version,
        "root_key_fingerprint_sha256": fingerprint,
        "verification_profile": selected_profile,
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


def test_signed_root_chain_allows_profiled_active_judge_key(tmp_path: Path):
    checkpoint, root, attestation = _write_chain(tmp_path)
    result = _verify(checkpoint, root, attestation)
    assert result["decision"] == "VERIFIED_ALLOW"
    assert result["root_version"] == 1
    assert result["authority_key_id"] == "test-judge-v1"
    assert result["verification_profile"] == PROFILE


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


def test_profile_rejects_sub_3072_modulus_and_alternate_exponent():
    weak = {"key_id": "weak", "n_hex": format((1 << 2047) + 1, "x"), "e": 65537}
    try:
        VERIFIER._parse_rsa_key(weak, "weak", PROFILE)
    except VERIFIER.VerificationError as exc:
        assert "below verification profile minimum" in str(exc)
    else:
        raise AssertionError("2048-bit-class RSA key was accepted")

    alternate_exponent = _key("alternate", exponent=3)
    try:
        VERIFIER._parse_rsa_key(alternate_exponent, "alternate", PROFILE)
    except VERIFIER.VerificationError as exc:
        assert "exponent violates verification profile" in str(exc)
    else:
        raise AssertionError("alternate RSA exponent was accepted")


def test_weakened_or_unknown_verification_profile_fails_closed(tmp_path: Path):
    weak_profile = dict(PROFILE)
    weak_profile["min_rsa_bits"] = 2048
    checkpoint, root, attestation = _write_chain(tmp_path, profile=weak_profile)
    try:
        _verify(checkpoint, root, attestation)
    except VERIFIER.VerificationError as exc:
        assert "weaker than required policy" in str(exc)
    else:
        raise AssertionError("weakened RSA verification profile was accepted")

    unknown_profile = dict(PROFILE)
    unknown_profile["version"] = 2
    checkpoint, root, attestation = _write_chain(tmp_path, profile=unknown_profile)
    try:
        _verify(checkpoint, root, attestation)
    except VERIFIER.VerificationError as exc:
        assert "unsupported RSA verification profile" in str(exc)
    else:
        raise AssertionError("unknown RSA verification profile was accepted")


def test_committed_release_checkpoint_is_fail_closed_until_real_root_is_provisioned():
    checkpoint = json.loads((ROOT / "security" / "review_root_checkpoint.json").read_text())
    assert checkpoint["schema"] == "centinal26-review-root-checkpoint-v1"
    assert checkpoint["provisioned"] is False
    assert checkpoint["root_key_fingerprint_sha256"] == "0" * 64
    assert checkpoint["verification_profile"] == PROFILE
