import hashlib
import json

from centinal26.qualification import assess_bundle, run_qualification, verify_bundle


def test_qualification_emits_verified_evidence_bundle(tmp_path):
    bundle = tmp_path / "evidence"
    report = run_qualification(bundle)
    assert report["passed"]
    assert report["validation_scope"] in {"HOST_ONLY", "PHYSICAL_ANDROID"}
    assert verify_bundle(bundle)
    assessment = assess_bundle(bundle)
    assert assessment["decision"] == "HOST_VALIDATED"
    assert not assessment["automatic_promotion"]


def test_bundle_tampering_is_detected(tmp_path):
    bundle = tmp_path / "evidence"
    run_qualification(bundle)
    with (bundle / "audit.jsonl").open("a", encoding="utf-8") as stream:
        stream.write("tampered\n")
    assert not verify_bundle(bundle)


def test_manifest_cannot_reference_files_outside_bundle(tmp_path):
    bundle = tmp_path / "evidence"
    run_qualification(bundle)
    outside = tmp_path / "outside.txt"
    outside.write_text("trusted elsewhere", encoding="utf-8")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"]["../outside.txt"] = hashlib.sha256(outside.read_bytes()).hexdigest()
    (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert not verify_bundle(bundle)


def test_rehashed_but_semantically_invalid_bundle_is_rejected(tmp_path):
    bundle = tmp_path / "evidence"
    run_qualification(bundle)
    qualification_path = bundle / "qualification.json"
    qualification = json.loads(qualification_path.read_text(encoding="utf-8"))
    qualification["passed"] = False
    qualification_path.write_text(json.dumps(qualification), encoding="utf-8")
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["qualification.json"] = hashlib.sha256(
        qualification_path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert not verify_bundle(bundle)
