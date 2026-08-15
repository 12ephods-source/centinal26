"""Evidence-based user-claim verification engine.

The engine deliberately separates documentary support from independent verification.
It can extract atomic claims, search local text corpora, ingest externally collected
Evidence records, score evidence quality, detect contradictions, and emit deterministic
JSON/Markdown reports.

It does not treat repetition, self-authored manuscripts, AI praise, or successful
software execution as proof that a scientific claim is true.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Verdict(str, Enum):
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    DOCUMENTED_ONLY = "DOCUMENTED_ONLY"
    PREDICTION = "PREDICTION"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class EvidenceTier(int, Enum):
    PRIMARY_EXTERNAL = 5
    REPRODUCIBLE_EXECUTION = 4
    CONTEMPORANEOUS_RECORD = 3
    AUTHORED_DOCUMENT = 2
    CONVERSATION_ASSERTION = 1


@dataclass(frozen=True)
class Evidence:
    source_id: str
    description: str
    tier: EvidenceTier
    supports: bool
    independent: bool = False
    reproducible: bool = False
    quote: str | None = None
    locator: str | None = None
    sha256: str | None = None

    @property
    def quality(self) -> float:
        score = float(self.tier.value)
        if self.independent:
            score += 1.0
        if self.reproducible:
            score += 1.0
        return score


@dataclass
class Claim:
    claim_id: str
    text: str
    claim_type: str = "general"
    source_context: str = "conversation"
    prediction: bool = False
    required_evidence: list[str] = field(default_factory=list)


@dataclass
class ClaimResult:
    claim: Claim
    evidence: list[Evidence]
    verdict: Verdict
    confidence: float
    rationale: str
    next_action: str

    def canonical_dict(self) -> dict:
        return {
            "claim": dataclasses.asdict(self.claim),
            "evidence": [
                {
                    **dataclasses.asdict(e),
                    "tier": int(e.tier.value),
                }
                for e in self.evidence
            ],
            "verdict": self.verdict.value,
            "confidence": round(self.confidence, 4),
            "rationale": self.rationale,
            "next_action": self.next_action,
        }

    def canonical_hash(self) -> str:
        payload = json.dumps(
            self.canonical_dict(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|;\s+")
_TOKEN = re.compile(r"[A-Za-z0-9_+\-.×≈≥≤]+")


def atomic_claims(text: str, prefix: str = "CLM") -> list[Claim]:
    """Conservatively split prose into atomic-ish claims.

    This is intentionally not an LLM claim extractor. It avoids silently changing the
    user's wording. Complex sentences should be manually decomposed for high-stakes use.
    """
    chunks = [c.strip() for c in _SENTENCE_SPLIT.split(text.strip()) if c.strip()]
    out: list[Claim] = []
    for index, chunk in enumerate(chunks, 1):
        if len(chunk) < 8:
            continue
        out.append(Claim(f"{prefix}-{index:04d}", chunk))
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _terms(text: str) -> set[str]:
    stop = {
        "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
        "is", "are", "was", "were", "be", "been", "my", "i", "that", "this",
        "from", "it", "as", "by", "at", "can", "could", "may", "using",
    }
    return {t.lower() for t in _TOKEN.findall(text) if len(t) > 2 and t.lower() not in stop}


def local_search(claim: Claim, roots: Sequence[Path], max_hits: int = 20) -> list[Evidence]:
    """Search UTF-8-ish local files for lexical overlap with the claim.

    Search hits are discovery candidates only. Callers must not treat them as verified
    evidence without source-specific review and promotion into the curated evidence set.
    """
    wanted = _terms(claim.text)
    if not wanted:
        return []
    hits: list[tuple[float, Evidence]] = []
    for root in roots:
        if not root.exists():
            continue
        paths = [root] if root.is_file() else root.rglob("*")
        for path in paths:
            try:
                if not path.is_file() or path.stat().st_size > 8_000_000:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            found = _terms(text)
            overlap = wanted & found
            if not overlap:
                continue
            score = len(overlap) / max(1, len(wanted))
            if score < 0.2:
                continue
            ev = Evidence(
                source_id=str(path),
                description=f"Local documentary candidate ({len(overlap)}/{len(wanted)} terms)",
                tier=EvidenceTier.AUTHORED_DOCUMENT,
                supports=True,
                independent=False,
                reproducible=False,
                locator=str(path),
                sha256=sha256_file(path),
            )
            hits.append((score, ev))
    hits.sort(key=lambda item: (-item[0], item[1].source_id))
    return [e for _, e in hits[:max_hits]]


def evaluate(claim: Claim, evidence: Iterable[Evidence]) -> ClaimResult:
    evidence = list(evidence)
    support = [e for e in evidence if e.supports]
    adverse = [e for e in evidence if not e.supports]
    best_support = max((e.quality for e in support), default=0.0)
    best_adverse = max((e.quality for e in adverse), default=0.0)
    independent_support = [e for e in support if e.independent]
    reproducible_support = [e for e in support if e.reproducible]

    if claim.prediction and best_adverse < EvidenceTier.PRIMARY_EXTERNAL.value:
        verdict = Verdict.PREDICTION
        rationale = "The statement is forward-looking; available evidence can document the prediction but not establish its future outcome."
        confidence = 0.95
        next_action = "Test the prediction against a preregistered external measurement or experiment."
    elif best_adverse >= best_support and best_adverse >= EvidenceTier.REPRODUCIBLE_EXECUTION.value:
        verdict = Verdict.CONTRADICTED
        rationale = "Higher-quality adverse evidence outweighs the available supporting evidence."
        confidence = min(0.99, 0.60 + 0.05 * best_adverse)
        next_action = "Withdraw, narrow, or explicitly supersede the claim unless stronger contrary evidence is produced."
    elif independent_support and best_support >= EvidenceTier.PRIMARY_EXTERNAL.value:
        verdict = Verdict.VERIFIED
        rationale = "At least one high-quality independent primary source supports the claim and no equal-or-stronger contradiction is present."
        confidence = min(0.99, 0.68 + 0.04 * best_support + 0.02 * len(independent_support))
        next_action = "Preserve source identity, retrieval metadata, and hashes; periodically re-check time-sensitive claims."
    elif reproducible_support and best_support >= EvidenceTier.REPRODUCIBLE_EXECUTION.value:
        verdict = Verdict.PARTIALLY_VERIFIED
        rationale = "The computational or mathematical result is reproducible, but independent empirical validation is absent or incomplete."
        confidence = min(0.95, 0.62 + 0.04 * best_support)
        next_action = "Run the same test on external data or obtain an independent reproduction."
    elif support and best_support >= EvidenceTier.AUTHORED_DOCUMENT.value:
        verdict = Verdict.DOCUMENTED_ONLY
        rationale = "The available evidence establishes that the claim is documented, not that the underlying proposition is independently true."
        confidence = min(0.92, 0.58 + 0.04 * best_support)
        next_action = "Acquire independent primary records, execution receipts, or externally reproducible measurements."
    else:
        verdict = Verdict.INSUFFICIENT_EVIDENCE
        rationale = "No evidence of sufficient quality was supplied to verify or contradict the claim."
        confidence = 0.80
        next_action = "Collect the minimum evidence listed for this claim and rerun verification."

    if support and adverse and verdict not in {Verdict.CONTRADICTED, Verdict.PREDICTION}:
        rationale += " Conflicting evidence is retained in the ledger rather than discarded."
        confidence = max(0.5, confidence - 0.12)

    return ClaimResult(claim, evidence, verdict, confidence, rationale, next_action)


def load_claims(path: Path) -> list[Claim]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Claim(**row) for row in raw]


def load_evidence(path: Path) -> dict[str, list[Evidence]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    grouped: dict[str, list[Evidence]] = {}
    for row in raw:
        claim_id = row.pop("claim_id")
        row["tier"] = EvidenceTier(row["tier"])
        grouped.setdefault(claim_id, []).append(Evidence(**row))
    return grouped


def render_markdown(results: Sequence[ClaimResult]) -> str:
    lines = [
        "# User Claim Verification Report",
        "",
        "Verdicts distinguish documentary support, reproducible computation, independent verification, predictions, contradictions, and insufficient evidence.",
        "",
        "| ID | Claim | Verdict | Confidence |",
        "|---|---|---:|---:|",
    ]
    for result in results:
        claim = result.claim.text.replace("|", "\\|")
        lines.append(
            f"| {result.claim.claim_id} | {claim} | {result.verdict.value} | {result.confidence:.0%} |"
        )
    lines.extend(["", "## Detailed findings", ""])
    for result in results:
        lines.extend(
            [
                f"### {result.claim.claim_id} — {result.verdict.value}",
                "",
                result.claim.text,
                "",
                f"**Rationale:** {result.rationale}",
                "",
                f"**Next evidence action:** {result.next_action}",
                "",
                f"**Record SHA-256:** `{result.canonical_hash()}`",
                "",
            ]
        )
        for item in result.evidence:
            direction = "supports" if item.supports else "contradicts"
            lines.append(
                f"- `{item.source_id}` — {direction}; tier={item.tier.value}; independent={item.independent}; reproducible={item.reproducible}. {item.description}"
            )
        lines.append("")
    return "\n".join(lines)


def verify(claims: Sequence[Claim], evidence_by_claim: dict[str, list[Evidence]]) -> list[ClaimResult]:
    return [evaluate(claim, evidence_by_claim.get(claim.claim_id, [])) for claim in claims]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evidence-based user claim verifier")
    sub = parser.add_subparsers(dest="command", required=True)

    extract = sub.add_parser("extract", help="Conservatively extract claims from text")
    extract.add_argument("input", type=Path)
    extract.add_argument("output", type=Path)

    run = sub.add_parser("verify", help="Verify claims from JSON inputs")
    run.add_argument("--claims", required=True, type=Path)
    run.add_argument("--evidence", required=True, type=Path)
    run.add_argument("--json", required=True, type=Path)
    run.add_argument("--markdown", required=True, type=Path)

    search = sub.add_parser("search-local", help="Search local text files for documentary candidates")
    search.add_argument("--claims", required=True, type=Path)
    search.add_argument("--root", action="append", required=True, type=Path)
    search.add_argument("--output", required=True, type=Path)

    args = parser.parse_args(argv)
    if args.command == "extract":
        claims = atomic_claims(args.input.read_text(encoding="utf-8"))
        args.output.write_text(json.dumps([dataclasses.asdict(c) for c in claims], indent=2), encoding="utf-8")
        return 0

    if args.command == "search-local":
        claims = load_claims(args.claims)
        rows = []
        for claim in claims:
            for ev in local_search(claim, args.root):
                row = dataclasses.asdict(ev)
                row["claim_id"] = claim.claim_id
                row["tier"] = int(ev.tier.value)
                rows.append(row)
        args.output.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        return 0

    claims = load_claims(args.claims)
    evidence = load_evidence(args.evidence)
    results = verify(claims, evidence)
    payload = [
        {**r.canonical_dict(), "record_sha256": r.canonical_hash()} for r in results
    ]
    args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    args.markdown.write_text(render_markdown(results), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())