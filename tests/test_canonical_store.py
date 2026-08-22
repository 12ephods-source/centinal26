from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from canonical_store import CanonicalStore, CanonicalStoreError  # noqa: E402

FIXTURE = ROOT / "examples" / "canonical_bundle.valid.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class CanonicalStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "canonical.db"
        self.store = CanonicalStore(self.db)

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def test_ingest_and_roundtrip(self) -> None:
        counts = self.store.ingest_bundle(load_fixture())
        self.assertEqual(counts, {"objects": 2, "provenance_events": 1, "filter_decisions": 1})
        obj = self.store.get_object("obj_summary")
        self.assertIsNotNone(obj)
        self.assertEqual(obj["payload"]["summary"], "derived example")
        self.assertEqual(self.store.stats()["canonical_objects"], 2)

    def test_identical_reingest_is_idempotent(self) -> None:
        self.store.ingest_bundle(load_fixture())
        counts = self.store.ingest_bundle(load_fixture())
        self.assertEqual(counts, {"objects": 0, "provenance_events": 0, "filter_decisions": 0})
        self.assertEqual(self.store.stats()["canonical_objects"], 2)

    def test_rejects_same_object_id_different_hash(self) -> None:
        self.store.ingest_bundle(load_fixture())
        changed = load_fixture()
        changed["objects"][0]["content_hash"] = "sha256:" + "c" * 64
        with self.assertRaisesRegex(CanonicalStoreError, "immutable object_id"):
            self.store.ingest_bundle(changed)
        obj = self.store.get_object("obj_raw_a")
        self.assertIsNotNone(obj)
        self.assertEqual(obj["content_hash"], "sha256:" + "a" * 64)

    def test_rejects_same_object_id_different_envelope(self) -> None:
        self.store.ingest_bundle(load_fixture())
        changed = load_fixture()
        changed["objects"][0]["payload"]["filename"] = "tampered.txt"
        with self.assertRaisesRegex(CanonicalStoreError, "different envelope"):
            self.store.ingest_bundle(changed)

    def test_invalid_bundle_rolls_back_without_partial_state(self) -> None:
        broken = load_fixture()
        broken["objects"][1]["provenance_ids"] = []
        with self.assertRaisesRegex(CanonicalStoreError, "bundle invariant failure"):
            self.store.ingest_bundle(broken)
        self.assertEqual(self.store.stats()["canonical_objects"], 0)

    def test_rejects_mutated_provenance_event(self) -> None:
        self.store.ingest_bundle(load_fixture())
        changed = load_fixture()
        changed["provenance_events"][0]["tool_version"] = "2"
        with self.assertRaisesRegex(CanonicalStoreError, "immutable provenance_event_id"):
            self.store.ingest_bundle(changed)

    def test_rejects_mutated_filter_decision(self) -> None:
        self.store.ingest_bundle(load_fixture())
        changed = load_fixture()
        changed["filter_decisions"][0]["reason"] = "changed"
        with self.assertRaisesRegex(CanonicalStoreError, "immutable filter_decision_id"):
            self.store.ingest_bundle(changed)

    def test_projection_is_rebuildable_and_non_authoritative(self) -> None:
        self.store.ingest_bundle(load_fixture())
        self.assertEqual(self.store.stats()["object_projection"], 0)
        self.assertEqual(self.store.rebuild_projection(), 2)
        rows = self.store.search_projection("derived example")
        self.assertEqual([row["object_id"] for row in rows], ["obj_summary"])
        value = self.store.conn.execute(
            "SELECT authoritative FROM object_projection WHERE object_id='obj_summary'"
        ).fetchone()[0]
        self.assertEqual(value, 0)
        self.store.conn.execute("DELETE FROM object_projection")
        self.store.conn.commit()
        self.assertIsNotNone(self.store.get_object("obj_summary"))
        self.assertEqual(self.store.rebuild_projection(), 2)

    def test_no_delete_command_surface(self) -> None:
        import canonical_store

        source = Path(canonical_store.__file__).read_text(encoding="utf-8")
        self.assertNotIn('sub.add_parser("delete")', source)

    def test_multiple_independent_bundles(self) -> None:
        self.store.ingest_bundle(load_fixture())
        second = copy.deepcopy(load_fixture())
        second["objects"][0]["object_id"] = "obj_raw_b"
        second["objects"][0]["content_hash"] = "sha256:" + "d" * 64
        second["objects"][0]["payload"] = {"filename": "second.txt"}
        second["objects"][1]["object_id"] = "obj_summary_b"
        second["objects"][1]["content_hash"] = "sha256:" + "e" * 64
        second["objects"][1]["related_ids"] = ["obj_raw_b"]
        second["objects"][1]["provenance_ids"] = ["prov_summary_b"]
        second["provenance_events"][0]["provenance_event_id"] = "prov_summary_b"
        second["provenance_events"][0]["input_ids"] = ["obj_raw_b"]
        second["provenance_events"][0]["output_ids"] = ["obj_summary_b"]
        second["filter_decisions"][0]["filter_decision_id"] = "filter_2"
        second["filter_decisions"][0]["input_object_id"] = "obj_raw_b"
        counts = self.store.ingest_bundle(second)
        self.assertEqual(counts["objects"], 2)
        self.assertEqual(self.store.stats()["canonical_objects"], 4)


if __name__ == "__main__":
    unittest.main()
