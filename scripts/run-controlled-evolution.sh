#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

if ! command -v python >/dev/null 2>&1; then
  printf 'BLOCKED: python is required.\n' >&2
  exit 2
fi

if ! command -v git >/dev/null 2>&1; then
  printf 'BLOCKED: git is required.\n' >&2
  exit 2
fi

if ! command -v goose >/dev/null 2>&1; then
  printf 'BLOCKED: goose CLI is not installed/configured.\n' >&2
  printf 'Centinal26 will not install or substitute an autonomous agent implicitly.\n' >&2
  exit 3
fi

set +e
python "$ROOT/scripts/controlled_evolution_loop.py" --repo "$ROOT" "$@"
rc=$?
set -e

git -C "$ROOT" worktree prune || true
exit "$rc"
