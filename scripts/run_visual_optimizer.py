"""Run the preservation-first visual optimizer from a device or CI worker."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from centinal26.image_provider import HTTPImageProvider, ProviderConfig
from centinal26.visual_evaluator import EvaluatorConfig, MultimodalEvaluator
from centinal26.visual_optimizer import VisualOptimizer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="canonical PNG to improve")
    parser.add_argument("--ledger", default="artifacts/visual_optimizer.jsonl")
    parser.add_argument("--output-dir", default="artifacts/visual_candidates")
    parser.add_argument("--api-url", default="https://api.openai.com/v1/images/edits")
    parser.add_argument("--model", default="gpt-image-1.5")
    parser.add_argument("--evaluator-model", default="gpt-5.1")
    parser.add_argument("--no-live-evaluator", action="store_true")
    args = parser.parse_args()
    image = Path(args.image)
    if not image.is_file():
        parser.error(f"image not found: {image}")
    evaluator = None
    if not args.no_live_evaluator:
        evaluator = MultimodalEvaluator(EvaluatorConfig(model=args.evaluator_model))
    provider = HTTPImageProvider(
        ProviderConfig(api_url=args.api_url, model=args.model, output_dir=args.output_dir),
        evaluator=evaluator,
    )
    optimizer = VisualOptimizer(provider, args.ledger)
    final = optimizer.optimize(str(image))
    print(
        json.dumps(
            {"status": "complete", "final_artifact": final, "ledger": args.ledger},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
