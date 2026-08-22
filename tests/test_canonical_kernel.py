import copy
import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_canonical_kernel", ROOT / "scripts" / "validate_canonical_kernel.py"
)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


def fixture():
    return json.loads((ROOT / "examples" / "canonical_bundle.valid.json").read_text())


class CanonicalKernelTests(unittest.TestCase):
    def test_valid_fixture_passes(self):
        self.assertEqual(mod.validate_bundle(fixture()), [])

    def test_derived_without_provenance_fails(self):
        data = fixture()
        data["objects"][1]["provenance_ids"] = []
        self.assertTrue(any("requires provenance" in e for e in mod.validate_bundle(data)))

    def test_projection_cannot_be_authoritative(self):
        data = fixture()
        obj = data["objects"][1]
        obj["authority_class"] = "PROJECTION"
        obj["authoritative"] = True
        self.assertTrue(any("projections must declare authoritative=false" in e for e in mod.validate_bundle(data)))

    def test_verified_claim_requires_evidence(self):
        data = fixture()
        claim = copy.deepcopy(data["objects"][1])
        claim["object_id"] = "claim_1"
        claim["type"] = "CLAIM"
        claim["content_hash"] = "sha256:" + "c" * 64
        claim["verification_status"] = "VERIFIED"
        claim["payload"] = {"proposition": "x", "evidence_ids": []}
        data["objects"].append(claim)
        data["provenance_events"][0]["output_ids"].append("claim_1")
        self.assertTrue(any("VERIFIED claim requires evidence_ids" in e for e in mod.validate_bundle(data)))

    def test_delete_is_not_dedupe_decision(self):
        data = fixture()
        data["filter_decisions"][0]["decision"] = "DELETE"
        self.assertTrue(any("illegal dedupe/filter decision" in e for e in mod.validate_bundle(data)))

    def test_reconstruction_cannot_claim_original(self):
        data = fixture()
        rec = copy.deepcopy(data["objects"][1])
        rec["object_id"] = "rec_1"
        rec["type"] = "RECONSTRUCTION"
        rec["content_hash"] = "sha256:" + "d" * 64
        rec["payload"] = {"originality_status": "ORIGINAL"}
        data["objects"].append(rec)
        data["provenance_events"][0]["output_ids"].append("rec_1")
        self.assertTrue(any("cannot claim original" in e for e in mod.validate_bundle(data)))

    def test_same_object_id_different_content_fails(self):
        data = fixture()
        dup = copy.deepcopy(data["objects"][0])
        dup["content_hash"] = "sha256:" + "e" * 64
        data["objects"].append(dup)
        self.assertTrue(any("reused with different content_hash" in e for e in mod.validate_bundle(data)))

    def test_unresolved_provenance_fails(self):
        data = fixture()
        data["objects"][1]["provenance_ids"] = ["missing"]
        self.assertTrue(any("unresolved provenance event" in e for e in mod.validate_bundle(data)))

    def test_event_must_name_object_as_output(self):
        data = fixture()
        data["provenance_events"][0]["output_ids"] = ["obj_raw_a"]
        self.assertTrue(any("does not name object as output" in e for e in mod.validate_bundle(data)))


if __name__ == "__main__":
    unittest.main()
