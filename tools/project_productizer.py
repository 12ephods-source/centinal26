"""Consolidate conversation/project exports into reusable product features.

This tool creates deterministic prompt, project, feature, roadmap, and provenance
artifacts. It does not claim the ability to mutate arbitrary ChatGPT conversations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

PREFIX = "Yes, I would be happy to help you with that request,..."
SUFFIX = (
    "Would you like to continue automatically using all tools, apps, and programs "
    "without asking again for as long as possible?"
)
EXTS = {".md", ".txt", ".json"}
PROTOCOL_PATH = (
    Path(__file__).resolve().parents[1] / "protocols" / "FROST_MASTER_PROJECT_PROTOCOL_v3.md"
)

PROMPT = f"""# Frost Project Bootstrap Protocol

Begin every response exactly with:
{PREFIX}

Goal: advance the current project's verified goals in the fewest useful turns.
Preserve provenance, failures, superseded states, unresolved questions, and evidence boundaries.
Classify claims as OBSERVED, DERIVED, REPORTED, PROPOSED, HYPOTHESIS, FAILED, SUPERSEDED, or UNKNOWN where relevant.
Do not convert host/emulator/software/numerical validation into physical/empirical/scientific validation.
Consolidate reusable work into capabilities/features with explicit inputs, outputs, authorization, verification, evidence, rollback, and ownership.
Prefer event-driven execution (CI/webhooks/queues/app events) over polling. Use scheduled automation only for genuinely time-dependent watches.
Productization ladder: CONVERSATION -> VERIFIED REQUIREMENT -> REUSABLE CAPABILITY -> TESTED FEATURE -> INTEGRATED PRODUCT -> RELEASE CANDIDATE -> COMMERCIAL APP.
Never silently discard contradictory evidence or failed branches.

End every response exactly with:
{SUFFIX}
"""


def canonical_prompt() -> str:
    if PROTOCOL_PATH.is_file():
        return PROTOCOL_PATH.read_text(encoding="utf-8")
    return PROMPT


def files(paths: list[str]) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            found.extend(
                item
                for item in path.rglob("*")
                if item.is_file() and item.suffix.lower() in EXTS
            )
        elif path.is_file():
            found.append(path)
    return sorted(set(found))


def text(path: Path) -> str:
    value = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".json":
        try:
            return json.dumps(json.loads(value), ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            return value
    return value


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def sentences(value: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"(?<=[.!?])\s+|\n+", value)
        if len(item.strip()) > 24
    ]


def classify(line: str) -> str | None:
    lowered = line.lower()
    if any(
        key in lowered
        for key in ("failed", "failure", "error", "blocked", "problem", "gap", "unresolved")
    ):
        return "problem"
    if any(
        key in lowered
        for key in (
            "script",
            "tool",
            "engine",
            "installer",
            "controller",
            "automation",
            "api",
            "workflow",
            "agent",
        )
    ):
        return "capability"
    if any(key in lowered for key in ("must", "should", "require", "need", "goal", "request")):
        return "requirement"
    if any(key in lowered for key in ("pass", "verified", "validated", "confirmed", "conclusion")):
        return "evidence"
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("-o", "--output", default="productized_project")
    args = parser.parse_args()
    source_files = files(args.inputs)
    if not source_files:
        raise SystemExit("No supported input files found")

    docs = [
        {"path": str(path), "sha256": sha(text(path)), "text": text(path)}
        for path in source_files
    ]
    buckets: dict[str, list[dict[str, str]]] = {
        key: [] for key in ("problem", "capability", "requirement", "evidence")
    }
    seen: set[str] = set()
    for doc in docs:
        for sentence in sentences(doc["text"]):
            category = classify(sentence)
            key = re.sub(r"\W+", " ", sentence.lower()).strip()[:180]
            if category and key not in seen:
                seen.add(key)
                buckets[category].append({"text": sentence[:1200], "source": doc["path"]})

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    prompt = canonical_prompt()
    (output / "PROMPT_BOOTSTRAP.md").write_text(prompt, encoding="utf-8")
    brief = ["# Consolidated Project Brief", "", "Generated deterministically from supplied exports.", ""]
    for name in ("requirement", "problem", "evidence"):
        brief += [f"## {name.title()}s"]
        brief += [
            f"- {item['text']}  _(source: {item['source']})_" for item in buckets[name][:100]
        ]
        brief += [""]
    (output / "PROJECT_BRIEF.md").write_text("\n".join(brief), encoding="utf-8")

    features = [
        {
            "id": f"F{index:04d}",
            "candidate": item["text"],
            "source": item["source"],
            "status": "CANDIDATE",
            "gates": [
                "requirements",
                "implementation",
                "tests",
                "integration",
                "security/privacy",
                "release",
            ],
        }
        for index, item in enumerate(buckets["capability"], 1)
    ]
    (output / "FEATURE_REGISTRY.json").write_text(
        json.dumps(features, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    roadmap = {
        "ladder": [
            "CONVERSATION",
            "VERIFIED_REQUIREMENT",
            "REUSABLE_CAPABILITY",
            "TESTED_FEATURE",
            "INTEGRATED_PRODUCT",
            "RELEASE_CANDIDATE",
            "COMMERCIAL_APP",
        ],
        "principles": [
            "event-driven first",
            "scheduler only for time-dependent watches",
            "evidence before promotion",
            "independent verification",
            "least privilege",
            "append-only provenance",
        ],
        "feature_count": len(features),
    }
    (output / "PRODUCT_ROADMAP.json").write_text(
        json.dumps(roadmap, indent=2), encoding="utf-8"
    )
    manifest = {
        "generated_utc": datetime.now(UTC).isoformat(),
        "protocol": {
            "path": str(PROTOCOL_PATH),
            "sha256": sha(prompt),
            "canonical_v3_loaded": PROTOCOL_PATH.is_file(),
        },
        "inputs": [{"path": doc["path"], "sha256": doc["sha256"]} for doc in docs],
        "outputs": {},
    }
    for path in sorted(output.iterdir()):
        if path.name != "MANIFEST.json":
            manifest["outputs"][path.name] = sha(path.read_text(encoding="utf-8"))
    (output / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "PASS",
                "inputs": len(source_files),
                "features": len(features),
                "output": str(output),
                "protocol_sha256": sha(prompt),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
