#!/usr/bin/env python3
"""Run the preservation-first visual optimizer from a device or CI worker."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from centinal26.image_provider import HTTPImageProvider, ProviderConfig
from centinal26.visual_optimizer import VisualOptimizer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="canonical PNG to improve")
    parser.add_argument("--ledger", default="artifacts/visual_optimizer.jsonl")
    parser.add_argument("--output-dir", default="artifacts/visual_candidates")
    parser.add_argument("--api-url", default="https://api.openai.com/v1/images/edits")
    parser.add_argument("--model", default="gpt-image-1.5")
    args = parser.parse_args()
    image = Path(args.image)
    if not image.is_file():
        parser.error(f"image not found: {image}")
    provider = HTTPImageProvider(ProviderConfig(api_url=args.api_url, model=args.model, output_dir=args.output_dir))
    optimizer = VisualOptimizer(provider, args.ledger)
    final = optimizer.optimize(str(image))
    print(json.dumps({"status": "complete", "final_artifact": final, "ledger": args.ledger}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
