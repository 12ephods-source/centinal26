"""Consolidate project exports into provenance-linked product candidates.

The Productizer consumes a versioned canonical protocol instead of embedding mutable
prompt text. It records protocol identity and hashes, preserves source provenance,
and never claims to mutate inaccessible ChatGPT conversation instructions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXTS = {".md", ".txt", ".json"}
DEFAULT_PROTOCOL = Path("protocols/FROST_MASTER_PROJECT_PROTOCOL_v2.md")
DEFAULT_METADATA = Path("protocols/frost_master_protocol_v2.json")
PROPAGATION_STATES = {
    "INSTALLED_VERIFIED",
    "OUTDATED",
    "CONFLICT",
    "PROPAGATION_BLOCKED_PLATFORM",
    "NOT_ATTEMPTED",
}


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_text(value: str) -> str:
    return sha_bytes(value.encode("utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_protocol(protocol_path: Path, metadata_path: Path) -> dict[str, Any]:
    protocol = read_text(protocol_path)
    metadata = json.loads(read_text(metadata_path))
    required = {"protocol_id", "version", "protocol_file", "required_hash_algorithm"}
    missing = sorted(required - metadata.keys())
    if missing:
        raise ValueError(f"Protocol metadata missing keys: {', '.join(missing)}")
    if metadata["required_hash_algorithm"].lower() != "sha256":
        raise ValueError("Only sha256 protocol identity is supported")
    states = set(metadata.get("propagation_states", []))
    if states != PROPAGATION_STATES:
        raise ValueError("Protocol propagation state schema does not match Productizer")
    return {
        "id": metadata["protocol_id"],
        "version": metadata["version"],
        "sha256": sha_text(protocol),
        "text": protocol,
        "metadata": metadata,
        "metadata_sha256": sha_text(read_text(metadata_path)),
        "source": str(protocol_path),
    }


def source_files(paths: list[str], excluded: set[Path]) -> list[Path]:
    found: set[Path] = set()
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            found.update(
                item
                for item in path.rglob("*")
                if item.is_file() and item.suffix.lower() in EXTS
            )
        elif path.is_file() and path.suffix.lower() in EXTS:
            found.add(path)
    return sorted(path for path in found if path.resolve() not in excluded)


def normalized_text(path: Path) -> str:
    value = read_text(path)
    if path.suffix.lower() == ".json":
        try:
            return json.dumps(json.loads(value), ensure_ascii=False, sort_keys=True, indent=2)
        except json.JSONDecodeError:
            return value
    return value


def sentences(value: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"(?<=[.!?])\s+|\n+", value)
        if len(item.strip()) > 24
    ]


def classify(line: str) -> str | None:
    lowered = line.lower()
    rules = (
        ("problem", ("failed", "failure", "error", "blocked", "problem", "gap", "unresolved")),
        ("capability", ("script", "tool", "engine", "installer", "controller", "automation", "api", "workflow", "agent")),
        ("requirement", ("must", "should", "require", "need", "goal", "request")),
        ("evidence", ("pass", "verified", "validated", "confirmed", "conclusion")),
    )
    for category, keys in rules:
        if any(key in lowered for key in keys):
            return category
    return None


def canonical_key(value: str) -> str:
    return re.sub(r"\W+", " ", value.casefold()).strip()[:240]


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    metadata_path = Path(args.protocol_metadata)
    protocol = load_protocol(protocol_path, metadata_path)
    excluded = {protocol_path.resolve(), metadata_path.resolve(), Path(args.output).resolve()}
    inputs = source_files(args.inputs, excluded)
    if not inputs:
        raise ValueError("No supported input files found")

    docs = []
    for path in inputs:
        value = normalized_text(path)
        docs.append({"path": str(path), "sha256": sha_text(value), "text": value})

    buckets: dict[str, list[dict[str, str]]] = {
        key: [] for key in ("problem", "capability", "requirement", "evidence")
    }
    seen: set[tuple[str, str]] = set()
    for doc in docs:
        for sentence in sentences(doc["text"]):
            category = classify(sentence)
            if category is None:
                continue
            identity = (category, canonical_key(sentence))
            if identity in seen:
                continue
            seen.add(identity)
            buckets[category].append(
                {"text": sentence[:1200], "source": doc["path"], "source_sha256": doc["sha256"]}
            )

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    bootstrap = (
        f"<!-- protocol_id={protocol['id']} version={protocol['version']} "
        f"sha256={protocol['sha256']} -->\n" + protocol["text"]
    )
    (output / "PROMPT_BOOTSTRAP.md").write_text(bootstrap, encoding="utf-8")

    protocol_record = {
        "protocol_id": protocol["id"],
        "version": protocol["version"],
        "sha256": protocol["sha256"],
        "metadata_sha256": protocol["metadata_sha256"],
        "source": protocol["source"],
        "installation_target": args.installation_target,
        "installation_status": "NOT_ATTEMPTED",
        "verification_status": "SOURCE_HASHED",
        "note": "Generated bootstrap only; no inaccessible ChatGPT instructions were mutated.",
    }
    write_json(output / "PROTOCOL_INSTALLATION.json", protocol_record)

    brief = ["# Consolidated Project Brief", "", "Generated from supplied exports with source hashes.", ""]
    for name in ("requirement", "problem", "evidence"):
        brief.append(f"## {name.title()}s")
        brief.extend(
            f"- {item['text']}  _(source: {item['source']}; sha256: {item['source_sha256']})_"
            for item in buckets[name][:100]
        )
        brief.append("")
    (output / "PROJECT_BRIEF.md").write_text("\n".join(brief), encoding="utf-8")

    features = [
        {
            "id": f"F{index:04d}",
            "candidate": item["text"],
            "source": item["source"],
            "source_sha256": item["source_sha256"],
            "status": "CANDIDATE_HEURISTIC",
            "promotion_requires_independent_review": True,
            "gates": [
                "requirements",
                "implementation",
                "tests",
                "integration",
                "security_privacy",
                "product_value",
                "release",
            ],
        }
        for index, item in enumerate(buckets["capability"], 1)
    ]
    write_json(output / "FEATURE_REGISTRY.json", features)

    roadmap = {
        "ladder": protocol["metadata"].get("productization_ladder", []),
        "principles": [
            "event-driven first",
            "evidence before promotion",
            "independent verification",
            "least privilege",
            "append-only provenance",
            "heuristic extraction is not product validation",
        ],
        "feature_count": len(features),
    }
    write_json(output / "PRODUCT_ROADMAP.json", roadmap)

    generated_at = datetime.now(UTC).isoformat()
    manifest: dict[str, Any] = {
        "schema_version": 2,
        "generated_at": generated_at,
        "protocol": {
            "id": protocol["id"],
            "version": protocol["version"],
            "sha256": protocol["sha256"],
            "metadata_sha256": protocol["metadata_sha256"],
        },
        "inputs": [{"path": doc["path"], "sha256": doc["sha256"]} for doc in docs],
        "outputs": {},
    }
    for path in sorted(output.iterdir()):
        if path.name != "MANIFEST.json" and path.is_file():
            manifest["outputs"][path.name] = sha_bytes(path.read_bytes())
    write_json(output / "MANIFEST.json", manifest)
    return {
        "status": "PASS",
        "inputs": len(inputs),
        "heuristic_feature_candidates": len(features),
        "protocol_id": protocol["id"],
        "protocol_version": protocol["version"],
        "protocol_sha256": protocol["sha256"],
        "output": str(output),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("-o", "--output", default="productized_project")
    parser.add_argument("--protocol", default=str(DEFAULT_PROTOCOL))
    parser.add_argument("--protocol-metadata", default=str(DEFAULT_METADATA))
    parser.add_argument("--installation-target", default="generated_project_package")
    args = parser.parse_args()
    try:
        result = build(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Productizer failed: {exc}") from exc
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
