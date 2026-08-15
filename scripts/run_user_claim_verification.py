#!/usr/bin/env python3
"""Run the user-claim verifier over curated and repository-local evidence.

Outputs are deterministic for a fixed repository tree and curated evidence file.
External/web evidence is intentionally ingested as curated Evidence records rather than
silently fetched at runtime, so every source can be reviewed and pinned.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import json
from pathlib import Path

from centinal26.claim_verifier import (
    Evidence,
    ClaimResult,
    load_claims,
    load_evidence,
    local_search,
    render_markdown,
    verify,
)


def _dedupe(items: list[Evidence]) -> list[Evidence]:
    seen: set[tuple] = set()
    out: list[Evidence] = []
    for item in items:
        key = (
            item.source_id,
            item.description,
            int(item.tier.value),
            item.supports,
            item.independent,
            item.reproducible,
            item.locator,
            item.sha256,
        )
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _result_payload(result: ClaimResult) -> dict:
    return {**result.canonical_dict(), "record_sha256": result.canonical_hash()}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def run(claims_path: Path, curated_path: Path, root: Path, outdir: Path) -> None:
    claims = load_claims(claims_path)
    curated = load_evidence(curated_path)
    evidence_by_claim: dict[str, list[Evidence]] = {}

    for claim in claims:
        combined = list(curated.get(claim.claim_id, []))
        combined.extend(local_search(claim, [root], max_hits=12))
        evidence_by_claim[claim.claim_id] = _dedupe(combined)

    results = verify(claims, evidence_by_claim)
    outdir.mkdir(parents=True, exist_ok=True)

    report_json = outdir / "claim_verification_report.json"
    report_md = outdir / "claim_verification_report.md"
    ledger_jsonl = outdir / "claim_ledger.jsonl"
    matrix_csv = outdir / "claim_matrix.csv"
    unresolved_md = outdir / "unresolved_evidence_requests.md"
    manifest = outdir / "evidence_manifest.json"

    report_json.write_text(
        json.dumps([_result_payload(r) for r in results], indent=2, sort_keys=True),
        encoding="utf-8",
    )
    report_md.write_text(render_markdown(results), encoding="utf-8")
    ledger_jsonl.write_text(
        "\n".join(json.dumps(_result_payload(r), sort_keys=True) for r in results) + "\n",
        encoding="utf-8",
    )

    with matrix_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow([
            "claim_id", "claim", "type", "verdict", "confidence",
            "evidence_count", "support_count", "adverse_count", "next_action",
            "record_sha256",
        ])
        for r in results:
            writer.writerow([
                r.claim.claim_id,
                r.claim.text,
                r.claim.claim_type,
                r.verdict.value,
                f"{r.confidence:.4f}",
                len(r.evidence),
                sum(1 for e in r.evidence if e.supports),
                sum(1 for e in r.evidence if not e.supports),
                r.next_action,
                r.canonical_hash(),
            ])

    unresolved = [
        r for r in results
        if r.verdict.value in {
            "INSUFFICIENT_EVIDENCE", "DOCUMENTED_ONLY", "PARTIALLY_VERIFIED", "PREDICTION"
        }
    ]
    lines = [
        "# Unresolved Evidence Requests",
        "",
        "Generated automatically from the current claim ledger.",
        "",
    ]
    for r in unresolved:
        lines.extend([
            f"## {r.claim.claim_id}",
            "",
            r.claim.text,
            "",
            f"Current verdict: **{r.verdict.value}**",
            "",
            "Minimum requested evidence:",
        ])
        for req in r.claim.required_evidence:
            lines.append(f"- {req}")
        lines.extend(["", f"Next action: {r.next_action}", ""])
    unresolved_md.write_text("\n".join(lines), encoding="utf-8")

    generated = [report_json, report_md, ledger_jsonl, matrix_csv, unresolved_md]
    manifest_payload = {
        "schema": "centinal26.user-claim-verification-manifest.v1",
        "claims_source": str(claims_path),
        "curated_evidence_source": str(curated_path),
        "repository_root": str(root),
        "claim_count": len(results),
        "verdict_counts": {
            verdict: sum(1 for r in results if r.verdict.value == verdict)
            for verdict in sorted({r.verdict.value for r in results})
        },
        "files": [
            {"path": p.name, "sha256": _sha256(p), "bytes": p.stat().st_size}
            for p in generated
        ],
    }
    manifest.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--claims", type=Path, default=Path("provenance/user_claims/2026-08-14_claims.json"))
    parser.add_argument("--evidence", type=Path, default=Path("provenance/user_claims/2026-08-14_evidence.json"))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--outdir", type=Path, default=Path("build/user_claim_verification"))
    args = parser.parse_args()
    run(args.claims, args.evidence, args.root, args.outdir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
