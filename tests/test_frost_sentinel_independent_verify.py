import importlib.util
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "tools/dfir/FROST_ANDROID_EVIDENCE_GUARDIAN_v3.1.sh"
MODULE = ROOT / "scripts/frost_sentinel_evidence_verify.py"
spec = importlib.util.spec_from_file_location("frost_sentinel_evidence_verify", MODULE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def _collect(tmp_path: pathlib.Path, *, fixture: bool = False) -> pathlib.Path:
    home = tmp_path / "home"
    base = tmp_path / "evidence"
    home.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "FROST_EVIDENCE_HOME": str(base),
            "CASE_ID": "CI-SENTINEL-001",
            "OPERATOR": "CI",
        }
    )
    if fixture:
        env["FROST_ANDROID_FIXTURE"] = "1"
    subprocess.run(
        ["bash", str(COLLECTOR), "collect"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return base


def _make_writable(path: pathlib.Path) -> None:
    subprocess.run(
        ["chmod", "-R", "u+rwX", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def host_evidence(tmp_path):
    base = _collect(tmp_path)
    try:
        yield base
    finally:
        _make_writable(tmp_path)


def test_independent_verifier_accepts_sealed_host_acquisition(host_evidence):
    result = mod.verify_base(host_evidence, require_runs=1)
    assert result["pass"] is True
    assert result["independent_integrity_corroboration"] is True
    assert result["forensic_attribution_established"] is False
    assert result["device_origin_independently_corroborated"] is False
    assert result["run_count"] == 1
    row = result["acquisition_timeline"][0]
    assert row["runtime_class"] == "HOST_OR_SESSION"
    assert row["claim_scope"] == "SOFTWARE_ONLY"
    assert row["device_origin_metadata_present"] is False


def test_independent_verifier_rejects_run_file_tamper(host_evidence):
    run_id = (host_evidence / "state/latest_run_id").read_text(encoding="utf-8").strip()
    target = host_evidence / "runs" / run_id / "meta" / "operator.txt"
    target.chmod(0o600)
    target.write_text("ALTERED\n", encoding="utf-8")
    result = mod.verify_base(host_evidence, require_runs=1)
    assert result["pass"] is False
    assert any("file_hash_mismatch:meta/operator.txt" in error for error in result["errors"])


def test_independent_verifier_rejects_ledger_tamper(host_evidence):
    ledger = host_evidence / "custody_chain.tsv"
    text = ledger.read_text(encoding="utf-8")
    ledger.write_text(text.replace("\tCI\t", "\tALTERED\t", 1), encoding="utf-8")
    result = mod.verify_base(host_evidence, require_runs=1)
    assert result["pass"] is False
    assert any("record_hash_mismatch" in error for error in result["errors"])


def test_independent_verifier_rejects_archive_tamper(host_evidence):
    archive = pathlib.Path(
        (host_evidence / "state/latest_archive").read_text(encoding="utf-8").strip()
    )
    archive.chmod(0o600)
    with archive.open("ab") as handle:
        handle.write(b"tamper")
    result = mod.verify_base(host_evidence, require_runs=1)
    assert result["pass"] is False
    assert any("archive_digest_mismatch" in error for error in result["errors"])


def test_android_fixture_remains_non_device_origin(tmp_path):
    base = _collect(tmp_path, fixture=True)
    try:
        result = mod.verify_base(base, require_runs=1)
        assert result["pass"] is True
        row = result["acquisition_timeline"][0]
        assert row["runtime_class"] == "ANDROID_FIXTURE"
        assert row["claim_scope"] == "ANDROID_LOGIC_AND_SOFTWARE"
        assert row["device_origin_metadata_present"] is False
        assert result["device_origin_independently_corroborated"] is False
    finally:
        _make_writable(tmp_path)


def test_two_acquisitions_form_verified_chain_and_timeline(tmp_path):
    base = _collect(tmp_path)
    _collect(tmp_path)
    try:
        result = mod.verify_base(base, require_runs=2)
        assert result["pass"] is True
        assert result["run_count"] == 2
        assert len(result["acquisition_timeline"]) == 2
        starts = [row["acquisition_started_utc"] for row in result["acquisition_timeline"]]
        assert starts == sorted(starts)
    finally:
        _make_writable(tmp_path)
