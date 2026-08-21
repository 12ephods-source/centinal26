import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "termux" / "library_cleaner" / "frost_library_cleanerd.py"

spec = importlib.util.spec_from_file_location("frost_library_cleanerd", SCRIPT)
assert spec is not None and spec.loader is not None
cleaner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cleaner
spec.loader.exec_module(cleaner)


def test_parse_ui_xml_and_exact_name_selection() -> None:
    xml = """<?xml version='1.0' encoding='UTF-8'?>
    <hierarchy rotation="0">
      <node text="Search files" resource-id="search" class="android.widget.EditText"
            bounds="[10,10][300,80]" />
      <node text="SHA256SUMS(20260821).txt" resource-id="" class="android.view.View"
            bounds="[20,100][500,160]" />
      <node text="" content-desc="Delete" resource-id="" class="android.widget.Button"
            bounds="[500,700][650,780]" />
    </hierarchy>
    """
    nodes = cleaner.parse_ui_xml(xml)
    assert len(nodes) == 3
    assert len(cleaner.exact_name_nodes(nodes, "SHA256SUMS(20260821).txt")) == 1
    assert len(cleaner.label_nodes(nodes, ["Delete"])) == 1


def test_candidate_classifier_allows_low_risk_sidecars() -> None:
    config = json.loads(json.dumps(cleaner.DEFAULT_CONFIG))
    assert cleaner.is_safe_candidate("SHA256SUMS(20260821).txt", config)
    assert cleaner.is_safe_candidate("artifact.zip.sha256", config)
    assert cleaner.is_safe_candidate("FILE_LIBRARY_CLEANUP_REPORT.md", config)


def test_candidate_classifier_denies_current_and_physical_evidence() -> None:
    config = json.loads(json.dumps(cleaner.DEFAULT_CONFIG))
    assert not cleaner.is_safe_candidate("CURRENT.sha256", config)
    assert not cleaner.is_safe_candidate("device_evidence.json", config)
    assert not cleaner.is_safe_candidate("worker_heartbeat.sha256", config)


def test_explicit_delete_name_is_still_subject_to_denylist() -> None:
    config = json.loads(json.dumps(cleaner.DEFAULT_CONFIG))
    config["explicit_delete_names"] = ["old_bundle.zip", "CURRENT_bundle.zip"]
    assert cleaner.is_safe_candidate("old_bundle.zip", config)
    assert not cleaner.is_safe_candidate("CURRENT_bundle.zip", config)


def test_candidate_names_deduplicates_filename_nodes() -> None:
    node = cleaner.UINode(
        text="artifact.zip.sha256",
        description="artifact.zip.sha256",
        resource_id="",
        class_name="android.view.View",
        bounds=(0, 0, 10, 10),
    )
    assert cleaner.candidate_names([node]) == ["artifact.zip.sha256"]


def test_sha256_file(tmp_path: Path) -> None:
    path = tmp_path / "sample.bin"
    path.write_bytes(b"abc")
    assert (
        cleaner.sha256_file(path)
        == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_archive_download_creates_copy_and_hash_ledger(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")
    archive = tmp_path / "archive"
    ledger = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(cleaner, "LEDGER_PATH", ledger)
    state = {"archived": {}, "deleted": {}, "last_cycle": None}
    config = json.loads(json.dumps(cleaner.DEFAULT_CONFIG))
    config["archive_dir"] = str(archive)

    destination, digest = cleaner.archive_download("source.txt", source, config, state)

    assert destination.exists()
    assert cleaner.sha256_file(destination) == digest
    assert state["archived"][digest] == str(destination)
    record = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert record["event"] == "ARCHIVED_BEFORE_DELETE"
    assert record["sha256"] == digest
    assert len(record["entry_sha256"]) == 64


def test_cycle_fails_closed_when_adb_is_unavailable(monkeypatch) -> None:
    config = json.loads(json.dumps(cleaner.DEFAULT_CONFIG))
    monkeypatch.setattr(cleaner, "ensure_adb", lambda: False)
    monkeypatch.setattr(cleaner, "load_state", lambda: {"archived": {}, "deleted": {}})
    result = cleaner.cycle(config, dry_run=False)
    assert result["deleted"] == []
    assert result["archived"] == []
    assert result["errors"] == ["ADB_NOT_CONNECTED"]
