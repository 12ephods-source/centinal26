import os

import pytest

from frost_core.manifest_policy import ManifestPolicy, ManifestPolicyError, build_manifest


def test_manifest_is_deterministic_and_records_permissions(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "b.txt").write_text("b", encoding="utf-8")
    (root / "a.txt").write_text("a", encoding="utf-8")
    first = build_manifest(root)
    second = build_manifest(root)
    assert first == second
    assert [entry["path"] for entry in first["entries"]] == ["a.txt", "b.txt"]
    assert first["file_count"] == 2
    assert all("mode" in entry for entry in first["entries"])
    assert len(first["manifest_sha256"]) == 64


def test_manifest_rejects_symlink_file(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = root / "target.txt"
    target.write_text("target", encoding="utf-8")
    try:
        (root / "link.txt").symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(ManifestPolicyError, match="symlink rejected"):
        build_manifest(root)


def test_manifest_rejects_symlink_directory(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = tmp_path / "outside"
    target.mkdir()
    (target / "secret.txt").write_text("outside", encoding="utf-8")
    try:
        (root / "outside-link").symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(ManifestPolicyError, match="symlink directory rejected"):
        build_manifest(root)


def test_manifest_rejects_hardlink(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    original = root / "original.txt"
    original.write_text("data", encoding="utf-8")
    try:
        os.link(original, root / "hard.txt")
    except OSError:
        pytest.skip("hardlinks unavailable")
    with pytest.raises(ManifestPolicyError, match="hardlink rejected"):
        build_manifest(root)


def test_manifest_enforces_file_count_limit(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "one").write_text("1", encoding="utf-8")
    (root / "two").write_text("2", encoding="utf-8")
    with pytest.raises(ManifestPolicyError, match="file-count limit"):
        build_manifest(root, policy=ManifestPolicy(max_files=1))


def test_manifest_enforces_total_byte_limit(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "large").write_bytes(b"12345")
    with pytest.raises(ManifestPolicyError, match="byte limit"):
        build_manifest(root, policy=ManifestPolicy(max_total_bytes=4))
