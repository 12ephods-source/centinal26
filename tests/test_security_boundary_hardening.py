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

# Test-only RSA key. Production trust material is provisioned outside the repository registry.
TEST_RSA_N = int(
    "c6acbcbac4956409542783048cc8f924c6c29a0b2c134d048be57828429071cbe348a12cf84287721d3b1e418be09018758638397e581826d3cbeabba7dd2ab6985ed1ab58facc658c9a18ef036402e84f5006a88f0054a99a231a073fbe9038210d23c87c51c8a1c954f1c46ac9f2c111864473c27a8d20dc8ddf88dd6143916c61e41ac1f032adcef0555b7a549671a4f1c85e311d262138013f24fba93e64497b2708d3fd2f690c2c7937d4834e466568e4db4b214046f584a21c24d50a6e8207d35b047a0f785fb1ae7c7c68283c8edd3ddd9e378908a56993a15034cdf81bd8130776920ec20671bbf46af2fa8be21be14ec0366795a2c1d02f8e5285b5",
    16,
)
TEST_RSA_D = int(
    "2c53c39b1f3bdeb14725b6b187f0da47c6920a3926691b04c1eaddb38be07b075ceb6a4ca48a817a6843b5b535ae91afe75ede4213aab79ec82025fc1f10b5543eac5f370e180d0d3640f681b37db7b959e2d6cd7a747e2f462d01446f484718c2e511e00c3eda1720dad34379f91b70d0c66694f6660e01703c364cece9e3df54070f05eac37f5af549413f9c3ee611d1db77e37f2d5c6bfa43f1991f94e4461fb913040442884619a27941c013899b9ac37b4a7fc7376aa5600497a08d701fddd7e2323742f18c779c902b063e1d0ef1717434b87f79560ac7741a515ed3b4283e5d1285f5eae8b2d42d52988d90ceda85b9b0da7e6ca0ac7ee29157463b51",
    16,
)
DIGESTINFO_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


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
    message = json.dumps(signed, sort_keys=True, separators=(",", ":")).encode()
    digest_info = DIGESTINFO_PREFIX + hashlib.sha256(message).digest()
    width = (TEST_RSA_N.bit_length() + 7) // 8
    padding = b"\xff" * (width - len(digest_info) - 3)
    encoded = b"\x00\x01" + padding + b"\x00" + digest_info
    signature = pow(int.from_bytes(encoded, "big"), TEST_RSA_D, TEST_RSA_N).to_bytes(width, "big")
    return base64.b64encode(signature).decode()


def write_review_attestation(
    tmp_path: Path,
    *,
    artifact_sha: str = "a" * 64,
    findings_sha: str = "b" * 64,
    expires_delta: timedelta = timedelta(hours=1),
) -> tuple[Path, Path]:
    authority = tmp_path / "review_authority.json"
    attestation = tmp_path / "review_attestation.json"
    authority.write_text(
        json.dumps(
            {
                "schema": "centinal26-review-authority-rsa-v1",
                "key_id": "test-frost-judge-rsa-v1",
                "n_hex": format(TEST_RSA_N, "x"),
                "e": 65537,
            }
        ),
        encoding="utf-8",
    )
    now = datetime.now(UTC)
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
    return authority, attestation


def run_attestation_verifier(
    authority: Path,
    attestation: Path,
    *,
    artifact_sha: str = "a" * 64,
    findings_sha: str = "b" * 64,
):
    return subprocess.run(
        [
            "python",
            str(ROOT / "scripts" / "verify_review_attestation.py"),
            "--authority",
            str(authority),
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
    authority, attestation = write_review_attestation(tmp_path)
    result = run_attestation_verifier(authority, attestation)
    assert result.returncode == 0, result.stdout
    output = json.loads(result.stdout)
    assert output["decision"] == "VERIFIED_ALLOW"
    assert output["verdict_id"] == "verdict:test-reviewed-artifact-v1"


def test_reviewed_risk_rejects_wrong_artifact_and_wrong_findings(tmp_path: Path):
    authority, attestation = write_review_attestation(tmp_path)
    wrong_artifact = run_attestation_verifier(authority, attestation, artifact_sha="c" * 64)
    wrong_findings = run_attestation_verifier(authority, attestation, findings_sha="d" * 64)
    assert wrong_artifact.returncode == 23
    assert "artifact identity mismatch" in wrong_artifact.stdout
    assert wrong_findings.returncode == 23
    assert "findings identity mismatch" in wrong_findings.stdout


def test_reviewed_risk_rejects_stale_or_unsigned_attestation(tmp_path: Path):
    authority, stale = write_review_attestation(tmp_path, expires_delta=timedelta(minutes=-2))
    stale_result = run_attestation_verifier(authority, stale)
    assert stale_result.returncode == 23
    assert "stale or expired" in stale_result.stdout

    authority, unsigned = write_review_attestation(tmp_path)
    payload = json.loads(unsigned.read_text(encoding="utf-8"))
    payload["signature_b64"] = ""
    unsigned.write_text(json.dumps(payload), encoding="utf-8")
    unsigned_result = run_attestation_verifier(authority, unsigned)
    assert unsigned_result.returncode == 23
    assert "signed attestation required" in unsigned_result.stdout


def test_registry_only_edits_are_not_execution_authority():
    worker = (TERMUX / "github_termux_worker_once.sh").read_text(encoding="utf-8")
    assert "reviewed_artifacts.json" not in worker
    assert "reviewed_findings_allow" not in worker
    assert "verify_review_attestation.py" in worker
    assert "signed_review_allow" in worker
    assert "Missing, stale, mismatched, unsigned, or invalid external Judge attestation fails closed" in worker
