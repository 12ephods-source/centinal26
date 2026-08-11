#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
evidence_root="${CENTINAL26_EVIDENCE_ROOT:-$HOME/centinal26-evidence}"
bundle="$evidence_root/qualification-$timestamp"

mkdir -p "$evidence_root"
centinal26 qualify --output "$bundle"
centinal26 verify-evidence "$bundle"
printf 'Evidence bundle: %s\n' "$bundle"
