from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "termux" / "openquest_citadel_canonical_closure.py"
MODULE = ROOT / "projects" / "openquest" / "the_devouring_citadel" / "module.json"


def load_tool():
    spec = importlib.util.spec_from_file_location("citadel_closure", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_module_variants() -> None:
    tool = load_tool()
    source = {"schemaVersion": 6, "worldVariables": {"x": 0}}
    variants = tool.module_variants(source)
    assert [name for name, _ in variants] == [
        "baseline_worldVariables",
        "documented_world_dot_variables",
    ]
    assert variants[0][1] is source
    assert variants[1][1]["world"] == {"variables": {"x": 0}}
    assert "worldVariables" not in variants[1][1]
    assert "world" not in source


def test_semantic_pass() -> None:
    tool = load_tool()
    assert tool.semantic_pass({"status": 200, "json": {"valid": True}})
    assert tool.semantic_pass({"status": 200, "json": {"issues": []}})
    assert not tool.semantic_pass({"status": 422, "json": {"valid": False}})
    assert not tool.semantic_pass(
        {"status": 200, "json": {"issues": [{"severity": "error"}]}}
    )


def test_frozen_identities() -> None:
    tool = load_tool()
    assert tool.RC1_PAYLOAD_BYTES == 3_458_656
    assert (
        tool.RC1_PAYLOAD_SHA256
        == "3e5a424e57b13f383d89daf1cf1337cdcb287771406a1c1242f33fe495c65c25"
    )
    assert (
        tool.CANDIDATE_OQMOD_SHA256
        == "9f2859183353d912b50638669a37e3d39f1110ecf7de3565b4632759015c5da0"
    )
    assert (
        tool.CANDIDATE_SEMANTIC_SHA256
        == "a536a6b72c772775d7d8d5214371643a7d6e212264c85ba0dc3b07315fd0e074"
    )
    assert (
        tool.PINNED_FILES["config/module-schema-v6.json"][1]
        == "8d9aa1b17aae8511b07c00b1f48f29bf1314ad63836608c78f96b7e76cc38de2"
    )


def test_repo_candidate_identity() -> None:
    tool = load_tool()
    data = json.loads(MODULE.read_text())
    assert data["schemaVersion"] == 6
    assert data["version"] == "1.3.0"
    assert data["packageId"] == "robert-frost/the-devouring-citadel"
    semantic = json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    assert tool.sha256_bytes(semantic) == tool.CANDIDATE_SEMANTIC_SHA256
