"""Deprecated multi-LLM FToE daemon.

This historical entrypoint aggregated persistent execution, outbound network
access, and provider credentials. It is superseded by the split-authority
``ftoe_secure_supervisor.py`` + ``ftoe_provider_broker.py`` architecture.
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
