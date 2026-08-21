"""Independent semantic evaluator for preservation-first visual optimization."""
from __future__ import annotations

import base64
import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .visual_optimizer import Defect, Scores


@dataclass(frozen=True)
class EvaluatorConfig:
    api_url: str = "https://api.openai.com/v1/responses"
    model: str = "gpt-5.1"
    api_key_env: str = "OPENAI_API_KEY"
    timeout_seconds: int = 180


HARD_GATES = (
    "image_integrity",
    "locked_foreground_identity",
    "no_unrequested_entities",
    "target_constraint",
)


class MultimodalEvaluator:
    """Compare canonical and candidate images with a separate multimodal call.

    The evaluator returns machine-readable evidence. Any missing/failed hard gate
    forces rejection-grade scores, independent of aesthetic quality.
    """

    def __init__(self, config: EvaluatorConfig | None = None):
        self.config = config or EvaluatorConfig()

    def evaluate(self, canonical: str, candidate: str, defect: Defect) -> dict:
        key = os.environ.get(self.config.api_key_env)
        if not key:
            raise RuntimeError(f"missing credential: {self.config.api_key_env}")
        canonical_path = Path(canonical)
        candidate_path = Path(candidate)
        for path in (canonical_path, candidate_path):
            if not path.is_file() or path.stat().st_size == 0:
                return self._failed("image_integrity", f"invalid image artifact: {path}")

        payload = {
            "model": self.config.model,
            "input": [{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": self._rubric(defect)},
                    {"type": "input_image", "image_url": self._data_url(canonical_path)},
                    {"type": "input_image", "image_url": self._data_url(candidate_path)},
                ],
            }],
            "text": {"format": {"type": "json_object"}},
        }
        request = urllib.request.Request(
            self.config.api_url,
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
            raw = json.loads(response.read().decode())
        evidence = self._extract_json(raw)
        return self._normalize(evidence)

    def _rubric(self, defect: Defect) -> str:
        return (
            "You are an independent visual QA evaluator. Image 1 is the canonical parent; "
            "Image 2 is the candidate. Evaluate only evidence visible in the images. "
            f"The single intended edit is: {defect.instruction}\n"
            "Return JSON with: hard_gates object containing booleans image_integrity, "
            "locked_foreground_identity, no_unrequested_entities, target_constraint; "
            "scores object with preservation, target_gain, collateral_drift each in [0,1]; "
            "observations array; confidence in [0,1]. Preservation measures unchanged locked "
            "content, target_gain measures improvement of only the intended edit, collateral_drift "
            "measures unrelated change. Be conservative under ambiguity. Do not reward aesthetics "
            "for violating cardinality, identity, source-target, orientation, or no-addition constraints."
        )

    def _normalize(self, evidence: dict) -> dict:
        gates = evidence.get("hard_gates", {})
        hard_pass = all(gates.get(name) is True for name in HARD_GATES)
        scores = evidence.get("scores", {})
        normalized = {
            "preservation": self._unit(scores.get("preservation", 0.0)),
            "target_gain": self._unit(scores.get("target_gain", 0.0)),
            "collateral_drift": self._unit(scores.get("collateral_drift", 1.0)),
        }
        if not hard_pass:
            normalized = {"preservation": 0.0, "target_gain": 0.0, "collateral_drift": 1.0}
        return {
            "status": "VERIFIED" if hard_pass else "HARD_GATE_FAIL",
            "hard_gates": gates,
            "hard_pass": hard_pass,
            "scores": normalized,
            "observations": evidence.get("observations", []),
            "confidence": self._unit(evidence.get("confidence", 0.0)),
        }

    @staticmethod
    def _unit(value: object) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _data_url(path: Path) -> str:
        encoded = base64.b64encode(path.read_bytes()).decode()
        return f"data:image/png;base64,{encoded}"

    @staticmethod
    def _extract_json(response: dict) -> dict:
        for item in response.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if text:
                    return json.loads(text)
        raise RuntimeError("evaluator returned no JSON output")

    @staticmethod
    def _failed(gate: str, reason: str) -> dict:
        gates = {name: name != gate for name in HARD_GATES}
        gates[gate] = False
        return {
            "status": "HARD_GATE_FAIL",
            "hard_gates": gates,
            "hard_pass": False,
            "scores": {"preservation": 0.0, "target_gain": 0.0, "collateral_drift": 1.0},
            "observations": [reason],
            "confidence": 1.0,
        }


def scores_from_evidence(evidence: dict) -> Scores:
    scores = evidence["scores"]
    return Scores(
        preservation=float(scores["preservation"]),
        target_gain=float(scores["target_gain"]),
        collateral_drift=float(scores["collateral_drift"]),
    )
