#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
umask 077

REPO="12ephods-source/centinal26"
REF="feature/termux-persistent-daemon-v1"
ROOT="${CENTINAL26_HOME:-$HOME/.centinal26}"
SRC="$ROOT/src"
BIN="$ROOT/bin"
CFG="$ROOT/config"
STATE="$ROOT/state"
LOGS="$ROOT/logs"
BACKUP="$ROOT/backup"
BOOT="$HOME/.termux/boot"
MANIFEST="$STATE/install_manifest.json"

say(){ printf '%s\n' "$*"; }
fail(){ say "ERROR: $*" >&2; exit 1; }
need(){ command -v "$1" >/dev/null 2>&1 || return 1; }
sha(){ sha256sum "$1" | awk '{print $1}'; }

say "[1/8] Centinal26 Termux environment validation"
[[ "${PREFIX:-}" == *"com.termux"* ]] || fail "Run this installer inside Termux."
mkdir -p "$SRC" "$BIN" "$CFG" "$STATE" "$LOGS" "$BACKUP" "$BOOT"

say "[2/8] Runtime dependencies"
pkg update -y >/dev/null
pkg install -y python git curl coreutils termux-api >/dev/null
if ! need gh; then pkg install -y gh >/dev/null || true; fi
need python || fail "python unavailable"
need git || fail "git unavailable"
need curl || fail "curl unavailable"
need sha256sum || fail "sha256sum unavailable"

say "[3/8] Fetch canonical source"
if [[ -d "$SRC/centinal26/.git" ]]; then
  git -C "$SRC/centinal26" remote set-url origin "https://github.com/$REPO.git"
  git -C "$SRC/centinal26" fetch --prune origin "$REF"
  if ! git -C "$SRC/centinal26" diff --quiet || ! git -C "$SRC/centinal26" diff --cached --quiet; then
    fail "Existing checkout is dirty; refusing to overwrite local changes."
  fi
  git -C "$SRC/centinal26" checkout -B "$REF" "origin/$REF"
else
  rm -rf "$SRC/centinal26.tmp"
  git clone --filter=blob:none --no-checkout "https://github.com/$REPO.git" "$SRC/centinal26.tmp"
  git -C "$SRC/centinal26.tmp" checkout "$REF"
  mv "$SRC/centinal26.tmp" "$SRC/centinal26"
fi
REV="$(git -C "$SRC/centinal26" rev-parse HEAD)"
[[ -n "$REV" ]] || fail "Could not resolve source revision"

say "[4/8] Safety qualification and payload verification"
for f in termux/centinal26_daemon.py termux/centinal26ctl.py termux/centinal26_daemon_service.sh; do
  [[ -f "$SRC/centinal26/$f" ]] || fail "Missing required payload: $f"
done
python -m py_compile "$SRC/centinal26/termux/centinal26_daemon.py" "$SRC/centinal26/termux/centinal26ctl.py"
bash -n "$SRC/centinal26/termux/centinal26_daemon_service.sh"
if grep -RInE '(^|[^[:alnum:]_])(eval|exec)[[:space:]]|curl[^\n]*\|[[:space:]]*(sh|bash)|wget[^\n]*\|[[:space:]]*(sh|bash)' \
  "$SRC/centinal26/termux/centinal26_daemon.py" "$SRC/centinal26/termux/centinal26ctl.py" "$SRC/centinal26/termux/centinal26_daemon_service.sh"; then
  fail "High-risk execution pattern detected in daemon payload"
fi

say "[5/8] Install/repair runtime"
for f in centinal26_daemon.py centinal26ctl.py centinal26_daemon_service.sh; do
  src="$SRC/centinal26/termux/$f"; dst="$BIN/$f"
  if [[ -f "$dst" ]]; then cp -a "$dst" "$BACKUP/${f}.$(date -u +%Y%m%dT%H%M%SZ)"; fi
  install -m 700 "$src" "$dst"
done

if [[ ! -f "$CFG/providers.json" ]]; then
cat > "$CFG/providers.json" <<'JSON'
{
  "providers": {},
  "policy": {
    "prefer_free": true,
    "require_explicit_configuration": true,
    "never_serialize_secrets": true,
    "selection_order": ["authorization", "fitness", "reliability", "evidence_quality", "cost"]
  }
}
JSON
chmod 600 "$CFG/providers.json"
fi

say "[6/8] Register boot/restart recovery"
cat > "$BOOT/start-centinal26.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
export CENTINAL26_HOME="$ROOT"
exec "$BIN/centinal26_daemon_service.sh" start
EOF
chmod 700 "$BOOT/start-centinal26.sh"

cat > "$BIN/centinal26-uninstall.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
"$BIN/centinal26_daemon_service.sh" stop || true
rm -f "$BOOT/start-centinal26.sh"
printf 'Daemon stopped and boot hook removed. Durable state preserved at %s\n' "$ROOT"
printf 'To remove everything after reviewing evidence/backups: rm -rf %q\n' "$ROOT"
EOF
chmod 700 "$BIN/centinal26-uninstall.sh"

say "[7/8] Start daemon"
export CENTINAL26_HOME="$ROOT"
"$BIN/centinal26_daemon_service.sh" restart

say "[8/8] Deterministic post-install verification"
sleep 1
STATUS="$($BIN/centinal26_daemon_service.sh status || true)"
printf '%s\n' "$STATUS"
printf '{"installed_at":%s,"source_revision":"%s","daemon_sha256":"%s","ctl_sha256":"%s","service_sha256":"%s"}\n' \
  "$(date +%s)" "$REV" "$(sha "$BIN/centinal26_daemon.py")" "$(sha "$BIN/centinal26ctl.py")" "$(sha "$BIN/centinal26_daemon_service.sh")" > "$MANIFEST.tmp"
mv "$MANIFEST.tmp" "$MANIFEST"
chmod 600 "$MANIFEST"
python "$BIN/centinal26ctl.py" status --limit 5 >/dev/null || fail "Control CLI verification failed"

say "CENTINAL26_TERMUX_INSTALL=PASS"
say "source_revision=$REV"
say "root=$ROOT"
say "control=$BIN/centinal26ctl.py"
say "service=$BIN/centinal26_daemon_service.sh"
say "uninstall=$BIN/centinal26-uninstall.sh"
say "Evidence state is durable in $STATE; this install does not claim device-tested status until independent device-origin verification is recorded."
