import json

from centinal26.qualification import run_qualification, verify_bundle


def test_qualification_emits_verified_evidence_bundle(tmp_path):
    bundle = tmp_path / "evidence"
    report = run_qualification(bundle)
    assert report["passed"]
    assert report["validation_scope"] in {"HOST_ONLY", "PHYSICAL_ANDROID"}
    assert verify_bundle(bundle)
    assert set(json.loads((bundle / "manifest.json").read_text())["files"]) == {
        "audit.jsonl",
        "qualification.json",
        "queue.sqlite3",
    }


def test_bundle_tampering_is_detected(tmp_path):
    bundle = tmp_path / "evidence"
    run_qualification(bundle)
    with (bundle / "audit.jsonl").open("a", encoding="utf-8") as stream:
        stream.write("tampered\n")
    assert not verify_bundle(bundle)
