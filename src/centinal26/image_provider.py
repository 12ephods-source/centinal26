"""Provider bridge for autonomous visual optimization.

Uses only Python stdlib. Credentials are read from environment and never
persisted. The generator is OpenAI-compatible; evaluation is local and
conservative so promotion fails closed unless measurable evidence is supplied.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from .visual_optimizer import Candidate, Defect, Scores


@dataclass(frozen=True)
class ProviderConfig:
    api_url: str = "https://api.openai.com/v1/images/edits"
    model: str = "gpt-image-1.5"
    api_key_env: str = "OPENAI_API_KEY"
    output_dir: str = "artifacts/visual_candidates"
    timeout_seconds: int = 180


class HTTPImageProvider:
    """Generate preservation-first image edits through an HTTP image API.

    Evaluation deliberately does not invent semantic scores. A sidecar JSON
    file may be produced by an independent evaluator; absent that evidence,
    the candidate receives fail-closed scores and cannot be promoted.
    """

    def __init__(self, config: ProviderConfig | None = None):
        self.config = config or ProviderConfig()
        self.output_dir = Path(self.config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, *, canonical_artifact: str, defect: Defect, locks: Sequence[str]) -> str:
        key = os.environ.get(self.config.api_key_env)
        if not key:
            raise RuntimeError(f"missing credential: {self.config.api_key_env}")
        source = Path(canonical_artifact)
        if not source.is_file():
            raise FileNotFoundError(source)
        prompt = self._prompt(defect, locks)
        boundary = "----centinal26-image-boundary"
        body = self._multipart(boundary, source, prompt)
        req = urllib.request.Request(
            self.config.api_url,
            data=body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        datum = payload["data"][0]
        if "b64_json" not in datum:
            raise RuntimeError("image provider returned no b64_json artifact")
        raw = base64.b64decode(datum["b64_json"])
        digest = sha256(raw).hexdigest()
        target = self.output_dir / f"{defect.key}-{digest[:16]}.png"
        target.write_bytes(raw)
        manifest = {
            "artifact": str(target),
            "sha256": digest,
            "parent": str(source),
            "defect": defect.key,
            "model": self.config.model,
        }
        target.with_suffix(".manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2))
        return str(target)

    def evaluate(self, *, canonical_artifact: str, candidate_artifact: str, defect: Defect, locks: Sequence[str]) -> Candidate:
        candidate = Path(candidate_artifact)
        evidence_path = candidate.with_suffix(".evaluation.json")
        if not evidence_path.exists():
            return Candidate(
                artifact=str(candidate),
                scores=Scores(preservation=0.0, target_gain=0.0, collateral_drift=1.0),
                evidence={"status": "UNVERIFIED", "reason": "independent evaluation missing"},
            )
        evidence = json.loads(evidence_path.read_text())
        scores = evidence.get("scores", {})
        return Candidate(
            artifact=str(candidate),
            scores=Scores(
                preservation=float(scores["preservation"]),
                target_gain=float(scores["target_gain"]),
                collateral_drift=float(scores["collateral_drift"]),
            ),
            evidence=evidence,
        )

    def _prompt(self, defect: Defect, locks: Sequence[str]) -> str:
        lock_text = "\n".join(f"- {lock}" for lock in locks)
        return (
            "Edit the supplied image. Make exactly one bounded correction.\n"
            f"TARGET: {defect.instruction}\n"
            "LOCKS (must remain visually unchanged):\n"
            f"{lock_text}\n"
            "Do not add unrelated content. Preserve composition and identity outside the target."
        )

    def _multipart(self, boundary: str, source: Path, prompt: str) -> bytes:
        chunks: list[bytes] = []

        def field(name: str, value: str) -> None:
            chunks.extend([
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode(),
                b"\r\n",
            ])

        field("model", self.config.model)
        field("prompt", prompt)
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="image"; filename="{source.name}"\r\n'.encode(),
            b"Content-Type: image/png\r\n\r\n",
            source.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ])
        return b"".join(chunks)
