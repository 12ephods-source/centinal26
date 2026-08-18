"""Deprecated direct-provider FToE daemon.

This entrypoint previously combined long-lived local execution, outbound HTTP,
and provider credentials in one process. That authority aggregation is no longer
an approved deployment path. Use ``scripts/ftoe_secure_supervisor.py`` instead.
"""

import sys

MESSAGE = (
    "Deprecated security-sensitive entrypoint. "
    "Use: python scripts/ftoe_secure_supervisor.py"
)


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
