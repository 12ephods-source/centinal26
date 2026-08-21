import json
import subprocess
import zipfile

import pytest

from frost_core.continuity_bundle import (
    ContinuityBundleError,
    create_signed_bundle,
    verify_signed_bundle,
)


def make_keys(tmp_path):
    private = tmp_path / "private.pem"
    public = tmp_path / "public.pem"
    try:
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "ED25519", "-out", str(private)],
            check=True,
            capture_output=True,
            timeout=30,
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pytest.skip("OpenSSL Ed25519 unavailable")
    return private, public


def proposal() -> dict:
    return {
        "schema": "frost.automation.continuity_migration_proposal.v1",
        "status": "PROPOSAL_ONLY",
        "source_digest": "a" * 64,
        "authority": {"execution_authority": False},
        "entities": [{"source_id": "project-1", "entity_type": "project"}],
        "relationships": [],
        "artifacts": [],
    }


def test_signed_bundle_round_trip(tmp_path) -> None:
    private, public = make_keys(tmp_path)
    bundle = tmp_path / "continuity.zip"
    receipt = create_signed_bundle(proposal(), bundle, private_key=private)
    verified = verify_signed_bundle(bundle, public_key=public)
    assert verified["status"] == "VERIFIED"
    assert verified["proposal"] == proposal()
    assert verified["bundle_sha256"] == receipt["bundle_sha256"]
    assert verified["payload_sha256"] == receipt["payload_sha256"]


def test_bundle_is_deterministic_for_same_payload_and_key(tmp_path) -> None:
    private, public = make_keys(tmp_path)
    one = tmp_path / "one.zip"
    two = tmp_path / "two.zip"
    first = create_signed_bundle(proposal(), one, private_key=private)
    second = create_signed_bundle(proposal(), two, private_key=private)
    assert first["bundle_sha256"] == second["bundle_sha256"]
    assert one.read_bytes() == two.read_bytes()
    assert verify_signed_bundle(two, public_key=public)["status"] == "VERIFIED"


def test_modified_payload_is_rejected_even_with_original_signature(tmp_path) -> None:
    private, public = make_keys(tmp_path)
    original = tmp_path / "original.zip"
    tampered = tmp_path / "tampered.zip"
    create_signed_bundle(proposal(), original, private_key=private)
    with zipfile.ZipFile(original, "r") as source, zipfile.ZipFile(tampered, "w") as target:
        for name in source.namelist():
            data = source.read(name)
            if name == "proposal.json":
                value = json.loads(data)
                value["status"] = "PROMOTED"
                data = json.dumps(
                    value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode()
            target.writestr(name, data)
    with pytest.raises(ContinuityBundleError, match="SHA-256 mismatch"):
        verify_signed_bundle(tampered, public_key=public)


def test_wrong_public_key_is_rejected(tmp_path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    private, _public = make_keys(first_dir)
    _other_private, other_public = make_keys(second_dir)
    bundle = tmp_path / "continuity.zip"
    create_signed_bundle(proposal(), bundle, private_key=private)
    with pytest.raises(ContinuityBundleError, match="OpenSSL operation failed"):
        verify_signed_bundle(bundle, public_key=other_public)


def test_extra_member_is_rejected(tmp_path) -> None:
    private, public = make_keys(tmp_path)
    bundle = tmp_path / "continuity.zip"
    modified = tmp_path / "extra.zip"
    create_signed_bundle(proposal(), bundle, private_key=private)
    with zipfile.ZipFile(bundle, "r") as source, zipfile.ZipFile(modified, "w") as target:
        for name in source.namelist():
            target.writestr(name, source.read(name))
        target.writestr("extra.txt", b"not allowed")
    with pytest.raises(ContinuityBundleError, match="member set"):
        verify_signed_bundle(modified, public_key=public)
