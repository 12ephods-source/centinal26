#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export CENTINAL26_SANDBOX_IMAGE="${CENTINAL26_SANDBOX_IMAGE:-centinal26-sandbox-root:local}"

if ! command -v python >/dev/null 2>&1; then
  printf 'BLOCKED: python is required.\n' >&2
  exit 2
fi

if ! command -v git >/dev/null 2>&1; then
  printf 'BLOCKED: git is required.\n' >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  printf 'BLOCKED_HARD_SANDBOX: Docker isolation is required; host execution fallback is disabled.\n' >&2
  exit 4
fi

if ! docker image inspect "$CENTINAL26_SANDBOX_IMAGE" >/dev/null 2>&1; then
  printf 'FROM scratch\n' | docker build --pull=false -t "$CENTINAL26_SANDBOX_IMAGE" - >/dev/null
fi

if ! command -v goose >/dev/null 2>&1; then
  printf 'BLOCKED: goose CLI is not installed/configured.\n' >&2
  printf 'Centinal26 will not install or substitute an autonomous agent implicitly.\n' >&2
  exit 3
fi

set +e
python "$ROOT/security/control_plane_guard.py" "$@"
rc=$?
set -e

git -C "$ROOT" worktree prune || true
exit "$rc"
