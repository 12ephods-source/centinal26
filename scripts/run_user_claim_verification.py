"""Run the user-claim verifier over curated and repository-local evidence.

Outputs are deterministic for a fixed repository tree and curated evidence file.
Lexical repository matches are emitted as discovery candidates, never as evidence that
can affect a verdict until explicitly reviewed and promoted into the curated ledger.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from centinal26.claim_verifier import (
    ClaimResult,
    Evidence,
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


def _search_candidates(claims, root: Path) -> list[dict]:
    rows: list[dict] = []
    for claim in claims:
        for ev in local_search(claim, [root], max_hits=12):
            source = ev.source_id.replace("\\", "/")
            if "/provenance/user_claims/" in f"/{source}" or "/build/user_claim_verification/" in f"/{source}":
                continue
            rows.append(
                {
                    "claim_id": claim.claim_id,
                    "source_id": ev.source_id,
                    "description": ev.description,
                    "locator": ev.locator,
                    "sha256": ev.sha256,
                    "status": "DISCOVERY_CANDIDATE_NOT_EVIDENCE",
                }
            )
    return rows


def run(claims_path: Path, curated_path: Path, root: Path, outdir: Path) -> None:
    claims = load_claims(claims_path)
    curated = load_evidence(curated_path)
    evidence_by_claim = {
        claim.claim_id: _dedupe(list(curated.get(claim.claim_id, []))) for claim in claims
    }
    candidates = _search_candidates(claims, root)
    results = verify(claims, evidence_by_claim)
    outdir.mkdir(parents=True, exist_ok=True)

    report_json = outdir / "claim_verification_report.json"
    report_md = outdir / "claim_verification_report.md"
    ledger_jsonl = outdir / "claim_ledger.jsonl"
    matrix_csv = outdir / "claim_matrix.csv"
    unresolved_md = outdir / "unresolved_evidence_requests.md"
    candidates_json = outdir / "documentary_search_candidates.json"
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
    candidates_json.write_text(json.dumps(candidates, indent=2, sort_keys=True), encoding="utf-8")

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
        r
        for r in results
        if r.verdict.value
        in {
            "INSUFFICIENT_EVIDENCE",
            "DOCUMENTED_ONLY",
            "PARTIALLY_VERIFIED",
            "PREDICTION",
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

    generated = [
        report_json,
        report_md,
        ledger_jsonl,
        matrix_csv,
        unresolved_md,
        candidates_json,
    ]
    manifest_payload = {
        "schema": "centinal26.user-claim-verification-manifest.v1",
        "claims_source": str(claims_path),
        "curated_evidence_source": str(curated_path),
        "repository_root": str(root),
        "claim_count": len(results),
        "search_candidate_count": len(candidates),
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
    parser.add_argument(
        "--claims",
        type=Path,
        default=Path("provenance/user_claims/2026-08-14_claims.json"),
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("provenance/user_claims/2026-08-14_evidence.json"),
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--outdir", type=Path, default=Path("build/user_claim_verification"))
    args = parser.parse_args()
    run(args.claims, args.evidence, args.root, args.outdir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())