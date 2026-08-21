import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "termux" / "library_cleaner" / "package_evidence.py"
spec = importlib.util.spec_from_file_location("library_cleaner_package_evidence", SCRIPT)
assert spec is not None and spec.loader is not None
packager = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = packager
spec.loader.exec_module(packager)


def test_package_evidence_builds_manifest_and_checksum(tmp_path: Path) -> None:
    app_home = tmp_path / "app"
    archive_dir = tmp_path / "archive"
    output_dir = tmp_path / "out"
    snapshots = app_home / "ui-snapshots"
    logs = app_home / "service-log"
    snapshots.mkdir(parents=True)
    logs.mkdir(parents=True)
    archive_dir.mkdir(parents=True)

    (app_home / "state.json").write_text('{"deleted": {}}\n', encoding="utf-8")
    (app_home / "archive-ledger.jsonl").write_text('{"event": "x"}\n', encoding="utf-8")
    (snapshots / "1.xml").write_text("<hierarchy />\n", encoding="utf-8")
    (logs / "current").write_text("service log\n", encoding="utf-8")
    archived = archive_dir / "item.txt"
    archived.write_text("payload", encoding="utf-8")

    zip_path, checksum_path, manifest = packager.package_evidence(
        app_home=app_home,
        archive_dir=archive_dir,
        output_dir=output_dir,
        include_archived_files=False,
        timestamp="20260821T000000Z",
    )

    assert zip_path.exists()
    assert checksum_path.exists()
    assert manifest["schema"] == "frost.library_cleaner.evidence.v1"
    assert manifest["archive_index"][0]["path"] == "item.txt"
    assert manifest["archive_index"][0]["sha256"] == hashlib.sha256(b"payload").hexdigest()

    checksum = checksum_path.read_text(encoding="utf-8").split()[0]
    assert checksum == packager.sha256_file(zip_path)

    with zipfile.ZipFile(zip_path) as bundle:
        names = set(bundle.namelist())
        assert "EVIDENCE_MANIFEST.json" in names
        assert "ARCHIVE_INDEX.json" in names
        assert "app/state.json" in names
        assert "app/archive-ledger.jsonl" in names
        assert "app/ui-snapshots/1.xml" in names
        assert "app/service-log/current" in names
        assert "archived/item.txt" not in names
        loaded = json.loads(bundle.read("EVIDENCE_MANIFEST.json"))
        assert loaded["include_archived_files"] is False


def test_package_evidence_can_include_archived_bytes(tmp_path: Path) -> None:
    app_home = tmp_path / "app"
    archive_dir = tmp_path / "archive"
    output_dir = tmp_path / "out"
    app_home.mkdir()
    archive_dir.mkdir()
    (archive_dir / "item.bin").write_bytes(b"abc")

    zip_path, _, _ = packager.package_evidence(
        app_home=app_home,
        archive_dir=archive_dir,
        output_dir=output_dir,
        include_archived_files=True,
        timestamp="20260821T000001Z",
    )

    with zipfile.ZipFile(zip_path) as bundle:
        assert bundle.read("archived/item.bin") == b"abc"
