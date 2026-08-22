#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$ROOT/install/2026-08-22__PERSISTENT_AUTOPILOT_TERMUX_v2.1.sh"
[[ -f "$TARGET" ]] || { echo 'missing v2.1 target'; exit 2; }
bash -n "$TARGET"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
out="$(HOME="$TMP" bash "$TARGET" --self-test 2>&1)"
printf '%s\n' "$out"
grep -q 'SELF_TEST PASS' <<<"$out"
grep -q 'refresh_if_needed' "$TARGET"
grep -q 'automation/persistent/kernel.py' "$TARGET"
grep -q 'installed_installer.sha256' "$TARGET"
grep -q 'device_boot_ok' "$TARGET"
grep -q 'security-context-json' "$TARGET"
echo 'persistent_autopilot_v2_1_tests=PASS'
