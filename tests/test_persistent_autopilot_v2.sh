#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$ROOT/install/2026-08-22__PERSISTENT_AUTOPILOT_TERMUX_v2.0.sh"
[[ -f "$TARGET" ]] || { echo 'missing target'; exit 2; }
bash -n "$TARGET"
out="$(HOME="$(mktemp -d)" bash "$TARGET" --self-test 2>&1)"
printf '%s\n' "$out"
grep -q 'SELF_TEST PASS' <<<"$out"
echo 'persistent_autopilot_v2_tests=PASS'
