from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERMUX = ROOT / "termux"

# Test-only 3072-bit RSA key. Production trust material is provisioned outside the repository registry.
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


def run_bash(script: str, *, home: Path, extra_env: dict[str, str] | None = None):
    env = os.environ.copy()
    env["HOME"] = str(home)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", "-c", script],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def _sign_message(message: bytes) -> str:
    digest_info = DIGESTINFO_PREFIX + hashlib.sha256(message).digest()
    width = (TEST_RSA_N.bit_length() + 7) // 8
    padding = b"\xff" * (width - len(digest_info) - 3)
    encoded = b"\x00\x01" + padding + b"\x00" + digest_info
    signature = pow(int.from_bytes(encoded, "big"), TEST_RSA_D, TEST_RSA_N).to_bytes(width, "big")
    return base64.b64encode(signature).decode()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sign_attestation(payload: dict[str, object]) -> str:
    signed = {
        key: payload[key]
        for key in (
            "schema",
            "authority_key_id",
            "verdict_id",
            "verdict",
            "verifier",
            "artifact_sha256",
            "findings_sha256",
            "issued_at",
            "expires_at",
        )
    }
    return _sign_message(_canonical_json(signed))


def _root_key(key_id: str) -> dict[str, object]:
    return {"key_id": key_id, "n_hex": format(TEST_RSA_N, "x"), "e": 65537}


def _root_fingerprint(key: dict[str, object]) -> str:
    return hashlib.sha256(_canonical_json(key)).hexdigest()


def _sign_root_metadata(payload: dict[str, object]) -> str:
    signed = {
        key: payload[key]
        for key in (
            "schema",
            "version",
            "root_key",
            "active_judge_keys",
            "revoked_key_ids",
            "issued_at",
            "expires_at",
        )
    }
    return _sign_message(_canonical_json(signed))


def write_review_attestation(
    tmp_path: Path,
    *,
    artifact_sha: str = "a" * 64,
    findings_sha: str = "b" * 64,
    expires_delta: timedelta = timedelta(hours=1),
) -> tuple[Path, Path, Path]:
    checkpoint = tmp_path / "review_root_checkpoint.json"
    root_metadata = tmp_path / "review_root_metadata.json"
    attestation = tmp_path / "review_attestation.json"
    now = datetime.now(UTC)
    root_key = _root_key("test-root-rsa-v1")
    judge_key = {
        **_root_key("test-frost-judge-rsa-v1"),
        "not_before": (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "not_after": (now + timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
    }
    checkpoint.write_text(
        json.dumps(
            {
                "schema": "centinal26-review-root-checkpoint-v1",
                "release": "1.0.0-test",
                "provisioned": True,
                "min_root_version": 1,
                "root_key_fingerprint_sha256": _root_fingerprint(root_key),
                "verification_profile": PROFILE,
            }
        ),
        encoding="utf-8",
    )
    root_payload: dict[str, object] = {
        "schema": "centinal26-review-root-metadata-v1",
        "version": 1,
        "root_key": root_key,
        "active_judge_keys": [judge_key],
        "revoked_key_ids": [],
        "issued_at": (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
    }
    root_payload["signature_b64"] = _sign_root_metadata(root_payload)
    root_metadata.write_text(json.dumps(root_payload), encoding="utf-8")
    payload: dict[str, object] = {
        "schema": "centinal26-reviewed-artifact-attestation-v1",
        "authority_key_id": "test-frost-judge-rsa-v1",
        "verdict_id": "verdict:test-reviewed-artifact-v1",
        "verdict": "VERIFIED",
        "verifier": "Frost Judge",
        "artifact_sha256": artifact_sha,
        "findings_sha256": findings_sha,
        "issued_at": (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        "expires_at": (now + expires_delta).isoformat().replace("+00:00", "Z"),
    }
    payload["signature_b64"] = sign_attestation(payload)
    attestation.write_text(json.dumps(payload), encoding="utf-8")
    return checkpoint, root_metadata, attestation


def run_attestation_verifier(
    checkpoint: Path,
    root_metadata: Path,
    attestation: Path,
    *,
    artifact_sha: str = "a" * 64,
    findings_sha: str = "b" * 64,
):
    return subprocess.run(
        [
            "python",
            str(ROOT / "scripts" / "verify_review_attestation.py"),
            "--checkpoint",
            str(checkpoint),
            "--root-metadata",
            str(root_metadata),
            "--attestation",
            str(attestation),
            "--artifact-sha256",
            artifact_sha,
            "--findings-sha256",
            findings_sha,
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def test_runtime_config_serializes_metadata_as_json_and_never_persists_token(tmp_path: Path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text(
        "#!/usr/bin/env bash\n"
        "if [ \"$1 $2 $3\" = \"auth token --hostname\" ]; then echo test-token; exit 0; fi\n"
        "if [ \"$1 $2\" = \"auth token\" ]; then echo test-token; exit 0; fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    gh.chmod(0o700)
    config = tmp_path / "config.json"
    helper = TERMUX / "github_runtime_config.sh"
    command = f'''
set -euo pipefail
source "{helper}"
github_runtime_write_config "{config}" "12ephods-source/centinal26" main "android-aarch64-123"
github_runtime_load_config "{config}"
printf '%s|%s|%s|%s\n' "$GITHUB_REPO" "$GITHUB_REF" "$AUTOMATION_DEVICE_ID" "$GITHUB_TOKEN"
'''
    result = run_bash(command, home=tmp_path, extra_env={"PATH": f"{bindir}:{os.environ['PATH']}"})
    assert result.returncode == 0, result.stdout
    assert "12ephods-source/centinal26|main|android-aarch64-123|test-token" in result.stdout
    data = json.loads(config.read_text(encoding="utf-8"))
    assert data == {
        "schema": "centinal26-github-worker-config-v1",
        "github_repo": "12ephods-source/centinal26",
        "github_ref": "main",
        "automation_device_id": "android-aarch64-123",
    }
    assert "token" not in config.read_text(encoding="utf-8").lower()


def test_runtime_config_rejects_noncanonical_repo_and_injection_shaped_device_id(tmp_path: Path):
    helper = TERMUX / "github_runtime_config.sh"
    config = tmp_path / "config.json"
    noncanonical = run_bash(
        f'source "{helper}"; github_runtime_write_config "{config}" "evil/repo" main device',
        home=tmp_path,
    )
    assert noncanonical.returncode != 0
    assert "BLOCKED_NONCANONICAL_REPO" in noncanonical.stdout

    injected = run_bash(
        f'''source "{helper}"; github_runtime_write_config "{config}" "12ephods-source/centinal26" main 'device$(touch /tmp/should-not-run)' ''',
        home=tmp_path,
    )
    assert injected.returncode != 0
    assert "BLOCKED_INVALID_DEVICE_ID" in injected.stdout
    assert not Path("/tmp/should-not-run").exists()


def test_termux_workers_do_not_source_mutable_runtime_config():
    for relative in (
        "github_termux_worker_once.sh",
        "report_after_reboot.sh",
        "intelligence_controller_github_worker_once.sh",
        "intelligence_controller_report_after_reboot.sh",
    ):
        text = (TERMUX / relative).read_text(encoding="utf-8")
        assert '/.automation_os_github/config"' not in text
        assert 'source "$CONFIG"' not in text
        assert "github_runtime_load_config" in text


def test_installers_do_not_persist_github_token():
    for relative in ("install_github_control.sh", "install_intelligence_github_control.sh"):
        text = (TERMUX / relative).read_text(encoding="utf-8")
        assert 'GITHUB_TOKEN="$TOKEN"' not in text
        assert "github_runtime_write_config" in text
        assert 'rm -f "$CFGDIR/config"' in text


def test_untrusted_candidate_auditor_has_no_flag_only_review_override():
    text = (ROOT / "scripts" / "audit_untrusted_candidate.py").read_text(encoding="utf-8")
    assert "--allow-reviewed-risk" not in text
    assert "EXPLICIT_REVIEW_OVERRIDE" not in text
    assert 'report["decision"] == "ALLOW_STATIC_ONLY"' in text


def test_reviewed_risk_requires_valid_signed_external_judge_attestation(tmp_path: Path):
    checkpoint, root_metadata, attestation = write_review_attestation(tmp_path)
    result = run_attestation_verifier(checkpoint, root_metadata, attestation)
    assert result.returncode == 0, result.stdout
    output = json.loads(result.stdout)
    assert output["decision"] == "VERIFIED_ALLOW"
    assert output["verdict_id"] == "verdict:test-reviewed-artifact-v1"
    assert output["root_version"] == 1
    assert output["verification_profile"] == PROFILE


def test_reviewed_risk_rejects_wrong_artifact_and_wrong_findings(tmp_path: Path):
    checkpoint, root_metadata, attestation = write_review_attestation(tmp_path)
    wrong_artifact = run_attestation_verifier(
        checkpoint, root_metadata, attestation, artifact_sha="c" * 64
    )
    wrong_findings = run_attestation_verifier(
        checkpoint, root_metadata, attestation, findings_sha="d" * 64
    )
    assert wrong_artifact.returncode == 23
    assert "artifact identity mismatch" in wrong_artifact.stdout
    assert wrong_findings.returncode == 23
    assert "findings identity mismatch" in wrong_findings.stdout


def test_reviewed_risk_rejects_stale_or_unsigned_attestation(tmp_path: Path):
    checkpoint, root_metadata, stale = write_review_attestation(
        tmp_path, expires_delta=timedelta(minutes=-2)
    )
    stale_result = run_attestation_verifier(checkpoint, root_metadata, stale)
    assert stale_result.returncode == 23
    assert "stale or expired" in stale_result.stdout

    checkpoint, root_metadata, unsigned = write_review_attestation(tmp_path)
    payload = json.loads(unsigned.read_text(encoding="utf-8"))
    payload["signature_b64"] = ""
    unsigned.write_text(json.dumps(payload), encoding="utf-8")
    unsigned_result = run_attestation_verifier(checkpoint, root_metadata, unsigned)
    assert unsigned_result.returncode == 23
    assert "attestation signature_b64 required" in unsigned_result.stdout


def test_registry_only_edits_are_not_execution_authority():
    worker = (TERMUX / "github_termux_worker_once.sh").read_text(encoding="utf-8")
    assert "reviewed_artifacts.json" not in worker
    assert "reviewed_findings_allow" not in worker
    assert "verify_review_attestation.py" in worker
    assert "signed_review_allow" in worker
    assert "Missing, stale, mismatched, unsigned, or invalid external Judge attestation fails closed" in worker
