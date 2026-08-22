#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
umask 077
REPO="12ephods-source/centinal26"; REF="feature/termux-persistent-daemon-v1"
ROOT="${CENTINAL26_HOME:-$HOME/.centinal26}"; SRC="$ROOT/src"; BIN="$ROOT/bin"; CFG="$ROOT/config"; STATE="$ROOT/state"; LOGS="$ROOT/logs"; BACKUP="$ROOT/backup"; BOOT="$HOME/.termux/boot"
say(){ printf '%s\n' "$*"; }; fail(){ say "ERROR: $*" >&2; exit 1; }; need(){ command -v "$1" >/dev/null 2>&1; }; sha(){ sha256sum "$1"|awk '{print $1}'; }
[[ "${PREFIX:-}" == *com.termux* ]] || fail "Run inside Termux"
mkdir -p "$SRC" "$BIN" "$CFG" "$STATE" "$LOGS" "$BACKUP" "$BOOT"
say "[1/7] dependencies"; pkg update -y >/dev/null; pkg install -y python git curl coreutils termux-api >/dev/null; need gh || pkg install -y gh >/dev/null || true
say "[2/7] source"; if [[ -d "$SRC/centinal26/.git" ]]; then git -C "$SRC/centinal26" fetch --prune origin "$REF"; git -C "$SRC/centinal26" diff --quiet && git -C "$SRC/centinal26" diff --cached --quiet || fail "dirty checkout"; git -C "$SRC/centinal26" checkout -B "$REF" "origin/$REF"; else git clone --branch "$REF" --single-branch "https://github.com/$REPO.git" "$SRC/centinal26"; fi; REV=$(git -C "$SRC/centinal26" rev-parse HEAD)
say "[3/7] qualification"; FILES=(centinal26_daemon.py centinal26ctl.py centinal26_daemon_service.sh centinal26_improvement_cycle.py centinal26_guardian.py); for f in "${FILES[@]}"; do [[ -f "$SRC/centinal26/termux/$f" ]]||fail "missing $f"; done; python -m py_compile "$SRC/centinal26/termux/centinal26_daemon.py" "$SRC/centinal26/termux/centinal26ctl.py" "$SRC/centinal26/termux/centinal26_improvement_cycle.py" "$SRC/centinal26/termux/centinal26_guardian.py"; bash -n "$SRC/centinal26/termux/centinal26_daemon_service.sh"
if grep -RInE 'curl[^\n]*\|[[:space:]]*(sh|bash)|wget[^\n]*\|[[:space:]]*(sh|bash)' "$SRC/centinal26/termux/centinal26_"*; then fail "pipe-to-shell pattern detected"; fi
say "[4/7] install"; for f in "${FILES[@]}"; do src="$SRC/centinal26/termux/$f"; dst="$BIN/$f"; [[ ! -f "$dst" ]]||cp -a "$dst" "$BACKUP/${f}.$(date -u +%Y%m%dT%H%M%SZ)"; install -m 700 "$src" "$dst"; done
[[ -f "$CFG/providers.json" ]]||{ cp "$SRC/centinal26/termux/providers.example.json" "$CFG/providers.json"; chmod 600 "$CFG/providers.json"; }
cat > "$BIN/centinal26_guardian_service.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="${ROOT}"; PID="${ROOT}/state/guardian.pid"; STOP="${ROOT}/state/GUARDIAN_STOP"
alive(){ [[ -f "\$PID" ]] && kill -0 "\$(cat "\$PID" 2>/dev/null)" 2>/dev/null; }
case "\${1:-start}" in
 start) alive && exit 0; rm -f "\$STOP"; nohup python "${BIN}/centinal26_guardian.py" >>"${LOGS}/guardian-supervisor.log" 2>&1 & echo \$! >"\$PID";;
 stop) touch "\$STOP"; alive && kill "\$(cat "\$PID")" || true; rm -f "\$PID";;
 restart) "\$0" stop; sleep 1; "\$0" start;;
 status) alive && echo "guardian-running pid=\$(cat "\$PID")" || { echo guardian-stopped; exit 1; };;
 *) exit 2;; esac
EOF
chmod 700 "$BIN/centinal26_guardian_service.sh"
cat > "$BOOT/start-centinal26.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
export CENTINAL26_HOME="$ROOT"
"$BIN/centinal26_daemon_service.sh" start
exec "$BIN/centinal26_guardian_service.sh" start
EOF
chmod 700 "$BOOT/start-centinal26.sh"
cat > "$BIN/centinal26-uninstall.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
"$BIN/centinal26_guardian_service.sh" stop || true
"$BIN/centinal26_daemon_service.sh" stop || true
rm -f "$BOOT/start-centinal26.sh"
printf 'Stopped; durable state preserved at %s\n' "$ROOT"
EOF
chmod 700 "$BIN/centinal26-uninstall.sh"
say "[5/7] start"; export CENTINAL26_HOME="$ROOT"; "$BIN/centinal26_daemon_service.sh" restart; "$BIN/centinal26_guardian_service.sh" restart
say "[6/7] verify"; sleep 2; "$BIN/centinal26_daemon_service.sh" status >/dev/null; "$BIN/centinal26_guardian_service.sh" status >/dev/null; python "$BIN/centinal26ctl.py" status --limit 5 >/dev/null
printf '{"installed_at":%s,"source_revision":"%s","daemon_sha256":"%s","guardian_sha256":"%s"}\n' "$(date +%s)" "$REV" "$(sha "$BIN/centinal26_daemon.py")" "$(sha "$BIN/centinal26_guardian.py")" > "$STATE/install_manifest.json.tmp"; mv "$STATE/install_manifest.json.tmp" "$STATE/install_manifest.json"; chmod 600 "$STATE/install_manifest.json"
say "[7/7] complete"; say "CENTINAL26_TERMUX_INSTALL=PASS"; say "source_revision=$REV"; say "reconcile_interval=1800s"; say "daemon=$BIN/centinal26_daemon_service.sh"; say "guardian=$BIN/centinal26_guardian_service.sh"; say "control=$BIN/centinal26ctl.py"; say "No device-tested promotion is implied until independent device-origin verification passes."
