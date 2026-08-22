from pathlib import Path

import pytest

from centinal26.dedupe_organizer_adapter import (
    DedupeOrganizerAdapter,
    DedupeOrganizerAdapterError,
    supported_operations,
)


def test_simple_operations_are_fixed_and_parameter_free(tmp_path: Path) -> None:
    adapter = DedupeOrganizerAdapter(allowed_scan_roots=[tmp_path])
    invocation = adapter.invocation("organizer.status")
    assert invocation.argv == ("dedupe-organizer", "status")

    with pytest.raises(DedupeOrganizerAdapterError):
        adapter.invocation("organizer.status", {"unexpected": "value"})


def test_scan_is_forced_read_only_and_inside_configured_root(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    nested = root / "nested"
    nested.mkdir(parents=True)
    adapter = DedupeOrganizerAdapter(allowed_scan_roots=[root])

    invocation = adapter.invocation("organizer.scan", {"path": str(nested)})
    assert invocation.argv == (
        "dedupe-organizer",
        "scan",
        str(nested.resolve()),
        "--no-organize",
    )


def test_scan_rejects_outside_root(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    adapter = DedupeOrganizerAdapter(allowed_scan_roots=[allowed])

    with pytest.raises(DedupeOrganizerAdapterError, match="outside configured roots"):
        adapter.invocation("organizer.scan", {"path": str(outside)})


def test_mutating_operations_are_not_exposed(tmp_path: Path) -> None:
    adapter = DedupeOrganizerAdapter(allowed_scan_roots=[tmp_path])
    for operation in (
        "organizer.quarantine",
        "organizer.restore",
        "organizer.delete",
        "shell",
        "exec",
    ):
        with pytest.raises(DedupeOrganizerAdapterError, match="not allowlisted"):
            adapter.invocation(operation)


def test_supported_operations_match_contract() -> None:
    operations = set(supported_operations())
    assert "organizer.scan" in operations
    assert "organizer.status" in operations
    assert "organizer.doctor" in operations
    assert "organizer.duplicates" in operations
    assert "organizer.near_duplicates" in operations
    assert "organizer.audit_verify" in operations
    assert "organizer.manifest" in operations
    assert "organizer.export_state" in operations
    assert "organizer.quarantine" not in operations
    assert "organizer.restore" not in operations


def test_executable_cannot_be_path_injected(tmp_path: Path) -> None:
    with pytest.raises(DedupeOrganizerAdapterError, match="fixed command name"):
        DedupeOrganizerAdapter(executable="/tmp/evil", allowed_scan_roots=[tmp_path])
