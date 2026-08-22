#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

VERSION="2.1.1"
REPO="${CENTINAL26_ROOT:-$HOME/centinal26}"
BASE_COMMIT="efa0ecceab06ae56e166917daadb4a39c5e8d748"
BASE_REL="install/2026-08-22__PERSISTENT_AUTOPILOT_TERMUX_v2.1.sh"
BASE_BLOB="d5ef6ae341c9666ef0d6d6b1dbbc82513317d51d"
RECOVERY_REL="install/2026-08-22__WORKER_AUTORECOVERY_TERMUX_v1.0.sh"
TMP="${TMPDIR:-${PREFIX:-/tmp}/tmp}/frost-persistent-v211-$$.sh"
trap 'rm -f "$TMP"' EXIT

if [[ "${1:-}" == "--version" ]]; then
  printf '%s\n' "$VERSION"
  exit 0
fi

[[ -d "$REPO/.git" ]] || { printf 'ERROR: canonical repository missing: %s\n' "$REPO" >&2; exit 2; }
actual_blob="$(git -C "$REPO" rev-parse "$BASE_COMMIT:$BASE_REL" 2>/dev/null || true)"
[[ "$actual_blob" == "$BASE_BLOB" ]] || {
  printf 'ERROR: frozen v2.1 base identity mismatch expected=%s actual=%s\n' "$BASE_BLOB" "$actual_blob" >&2
  exit 2
}
git -C "$REPO" show "$BASE_COMMIT:$BASE_REL" > "$TMP"
chmod 700 "$TMP"
bash -n "$TMP"

# Preserve the already-qualified v2.1 behavior exactly, then add the bounded
# worker-visibility recovery layer. The frozen base sees this wrapper as the
# canonical path, so its existing hash-based self-refresh remains functional.
bash "$TMP" "$@"

RECOVERY="$REPO/$RECOVERY_REL"
[[ -f "$RECOVERY" ]] || { printf 'ERROR: worker autorecovery installer missing: %s\n' "$RECOVERY" >&2; exit 2; }
bash -n "$RECOVERY"
bash "$RECOVERY" "$@"

printf 'Persistent autopilot compatibility layer v%s complete\n' "$VERSION"
