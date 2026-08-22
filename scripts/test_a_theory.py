from __future__ import annotations

import argparse
import json
from pathlib import Path

from centinal26.test_a_theory import write_reproducibility_package


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded Test-a-Theory v1 gates")
    parser.add_argument("model", type=Path, help="test-a-theory/model-v1 JSON input")
    parser.add_argument("output", type=Path, help="directory for reproducibility package")
    args = parser.parse_args()

    try:
        payload = json.loads(args.model.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("model root must be a JSON object")
        report = write_reproducibility_package(payload, args.output)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, sort_keys=True))
        return 2

    print(json.dumps(report.as_dict(), sort_keys=True))
    return 0 if report.verdict == "PASS_DECLARED_GATES" else 1


if __name__ == "__main__":
    raise SystemExit(main())
