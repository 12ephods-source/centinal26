"""Frost Automation OS enrollment package validation stub.

Checks local prerequisites before a worker is enrolled.
"""

import json
import platform


def collect_environment():
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "status": "discovery_only"
    }


if __name__ == "__main__":
    print(json.dumps(collect_environment(), indent=2))
