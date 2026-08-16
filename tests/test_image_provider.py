import json
from pathlib import Path

from centinal26.image_provider import HTTPImageProvider, ProviderConfig
from centinal26.visual_optimizer import Defect


def test_evaluation_fails_closed_without_independent_evidence(tmp_path: Path):
    candidate = tmp_path / "candidate.png"
    candidate.write_bytes(b"png")
    provider = HTTPImageProvider(ProviderConfig(output_dir=str(tmp_path)))
    result = provider.evaluate(
        canonical_artifact="parent.png",
        candidate_artifact=str(candidate),
        defect=Defect("x", "fix x"),
        locks=("lock",),
    )
    assert result.scores.preservation == 0.0
    assert result.scores.target_gain == 0.0
    assert result.scores.collateral_drift == 1.0
    assert result.evidence["status"] == "UNVERIFIED"


def test_evaluation_consumes_independent_evidence(tmp_path: Path):
    candidate = tmp_path / "candidate.png"
    candidate.write_bytes(b"png")
    evidence = {
        "status": "VERIFIED",
        "scores": {"preservation": 0.97, "target_gain": 0.12, "collateral_drift": 0.02},
    }
    candidate.with_suffix(".evaluation.json").write_text(json.dumps(evidence))
    provider = HTTPImageProvider(ProviderConfig(output_dir=str(tmp_path)))
    result = provider.evaluate(
        canonical_artifact="parent.png",
        candidate_artifact=str(candidate),
        defect=Defect("x", "fix x"),
        locks=("lock",),
    )
    assert result.scores.preservation == 0.97
    assert result.scores.target_gain == 0.12
    assert result.scores.collateral_drift == 0.02
