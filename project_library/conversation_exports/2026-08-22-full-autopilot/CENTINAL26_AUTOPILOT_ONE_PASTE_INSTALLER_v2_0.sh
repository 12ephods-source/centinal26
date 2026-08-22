#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
umask 077

# Centinal26 Full Autopilot one-paste installer v2.0
# Canonical source: 12ephods-source/centinal26 main
# Pinned audit baseline at bundle creation: be8a8f9d48a556712ed424b86274f1271c8195fb
# Run explicitly by pasting into Termux. It does NOT monitor or auto-execute clipboard contents.
# Host test: CENTINAL26_DRY_RUN=1 bash CENTINAL26_AUTOPILOT_ONE_PASTE_INSTALLER_v2_0.sh

REPO="${CENTINAL26_REPO:-12ephods-source/centinal26}"
REF="${CENTINAL26_REF:-main}"
ROOT="${CENTINAL26_HOME:-$HOME/.centinal26}"
SRC="$ROOT/src/centinal26"; BIN="$ROOT/bin"; CFG="$ROOT/config"; STATE="$ROOT/state"; LOGS="$ROOT/logs"; BACKUP="$ROOT/backup"; EVID="$ROOT/evidence"; REPORTS="$ROOT/reports"; BOOT="$HOME/.termux/boot"; DRY="${CENTINAL26_DRY_RUN:-0}"
say(){ printf '%s\n' "$*"; }; fail(){ say "ERROR: $*" >&2; exit 1; }; need(){ command -v "$1" >/dev/null 2>&1; }; sha(){ sha256sum "$1"|awk '{print $1}'; }
is_termux(){ [[ "${PREFIX:-}" == *com.termux* ]]; }
[[ "$DRY" == "1" ]] || is_termux || fail "Run inside Termux, or set CENTINAL26_DRY_RUN=1 for host testing."
mkdir -p "$SRC" "$BIN" "$CFG" "$STATE" "$LOGS" "$BACKUP" "$EVID/code_gate" "$REPORTS/code_gate"; [[ "$DRY" == "1" ]] || mkdir -p "$BOOT"
say "[1/9] dependency qualification"
if [[ "$DRY" != "1" ]]; then pkg update -y >/dev/null; pkg install -y python git coreutils curl >/dev/null; pkg install -y termux-api >/dev/null 2>&1 || true; need gh || pkg install -y gh >/dev/null 2>&1 || true; else need bash || fail "bash missing"; need python || need python3 || fail "python missing"; need git || fail "git missing"; need sha256sum || fail "sha256sum missing"; fi
say "[2/9] canonical source checkout/update"
if [[ "$DRY" == "1" ]]; then say "DRY_RUN: would clone/update https://github.com/$REPO.git ref=$REF into $SRC"; elif [[ -d "$SRC/.git" ]]; then git -C "$SRC" diff --quiet && git -C "$SRC" diff --cached --quiet || fail "Refusing to overwrite dirty checkout"; git -C "$SRC" fetch --prune origin "$REF"; git -C "$SRC" checkout -B "$REF" "origin/$REF"; else rm -rf "$SRC"; git clone --branch "$REF" --single-branch "https://github.com/$REPO.git" "$SRC"; fi
say "[3/9] locate canonical Termux capabilities"
FILES=(centinal26_daemon.py centinal26ctl.py centinal26_daemon_service.sh centinal26_improvement_cycle.py centinal26_guardian.py centinal26_code_gate.py)
if [[ "$DRY" == "1" ]]; then for f in "${FILES[@]}"; do say "DRY_RUN: require termux/$f"; done; else for f in "${FILES[@]}"; do [[ -f "$SRC/termux/$f" ]] || fail "Missing canonical termux/$f"; done; fi
say "[4/9] static qualification"
if [[ "$DRY" == "1" ]]; then say "DRY_RUN: python -m py_compile daemon ctl improvement guardian code_gate"; say "DRY_RUN: bash -n daemon service"; else python -m py_compile "$SRC/termux/centinal26_daemon.py" "$SRC/termux/centinal26ctl.py" "$SRC/termux/centinal26_improvement_cycle.py" "$SRC/termux/centinal26_guardian.py" "$SRC/termux/centinal26_code_gate.py"; bash -n "$SRC/termux/centinal26_daemon_service.sh"; grep -RInE 'curl[^\n]*\|[[:space:]]*(sh|bash)|wget[^\n]*\|[[:space:]]*(sh|bash)' "$SRC/termux/centinal26_"* && fail "Unsafe pipe-to-shell pattern detected" || true; fi
say "[5/9] install/update bounded capabilities"
if [[ "$DRY" != "1" ]]; then TS="$(date -u +%Y%m%dT%H%M%SZ)"; for f in "${FILES[@]}"; do src="$SRC/termux/$f"; dst="$BIN/$f"; [[ ! -f "$dst" ]] || cp -a "$dst" "$BACKUP/${f}.$TS"; install -m 700 "$src" "$dst"; done; [[ ! -f "$SRC/termux/providers.example.json" || -f "$CFG/providers.json" ]] || { cp "$SRC/termux/providers.example.json" "$CFG/providers.json"; chmod 600 "$CFG/providers.json"; }; printf '#!/data/data/com.termux/files/usr/bin/bash\nexec python "%s/centinal26_code_gate.py" "$@"\n' "$BIN" > "$BIN/code-gate"; chmod 700 "$BIN/code-gate"; fi
say "[6/9] install guardian + boot recovery"
if [[ "$DRY" != "1" ]]; then cat > "$BIN/centinal26_guardian_service.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$ROOT"; PID="$STATE/guardian.pid"; STOP="$STATE/GUARDIAN_STOP"
alive(){ [[ -f "\$PID" ]] && kill -0 "\$(cat "\$PID" 2>/dev/null)" 2>/dev/null; }
case "\${1:-start}" in start) alive && exit 0; rm -f "\$STOP"; nohup python "$BIN/centinal26_guardian.py" >>"$LOGS/guardian-supervisor.log" 2>&1 & echo \$! >"\$PID";; stop) touch "\$STOP"; alive && kill "\$(cat "\$PID")" || true; rm -f "\$PID";; restart) "\$0" stop; sleep 1; "\$0" start;; status) alive && echo "guardian-running pid=\$(cat "\$PID")" || { echo guardian-stopped; exit 1; };; *) exit 2;; esac
EOF
chmod 700 "$BIN/centinal26_guardian_service.sh"; cat > "$BOOT/start-centinal26.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
export CENTINAL26_HOME="$ROOT"
"$BIN/centinal26_daemon_service.sh" start
exec "$BIN/centinal26_guardian_service.sh" start
EOF
chmod 700 "$BOOT/start-centinal26.sh"; fi
say "[7/9] write full-autopilot policy"
POLICY="$CFG/full_autopilot_policy.json"
if [[ "$DRY" == "1" ]]; then say "DRY_RUN: would write $POLICY"; else cat > "$POLICY.tmp" <<'JSON'
{"schema_version":1,"mode":"full_autopilot","objective":"maximize useful verified project progress while minimizing unnecessary user labor","canonical_flow":["reconcile","rank_work","plan","execute","test","criticize","improve","independently_verify","record_evidence","update_state","continue"],"evidence_ownership":"USER_EVIDENCE","origin_is_separate_from_ownership":true,"lifecycle":["attempted","built","sandbox-tested","device-tested","production-ready"],"blocker_policy":"repair_fallback_or_watch_resume_then_continue_independent_work","progress_first":true,"defer_restrictive_cybersecurity_hardening_until_security_phase":true,"preserve_legacy_history":true,"never_fabricate_device_execution":true,"never_change_scientific_thresholds_to_force_pass":true}
JSON
mv "$POLICY.tmp" "$POLICY"; chmod 600 "$POLICY"; fi
say "[8/9] start + deterministic verification"
if [[ "$DRY" == "1" ]]; then say "DRY_RUN: would restart daemon + guardian and run code-gate --help + ctl status"; say "CENTINAL26_AUTOPILOT_DRY_RUN=PASS"; else export CENTINAL26_HOME="$ROOT"; "$BIN/centinal26_daemon_service.sh" restart; "$BIN/centinal26_guardian_service.sh" restart; "$BIN/code-gate" --help >/dev/null; sleep 2; "$BIN/centinal26_daemon_service.sh" status >/dev/null; "$BIN/centinal26_guardian_service.sh" status >/dev/null; python "$BIN/centinal26ctl.py" status --limit 5 >/dev/null; REV="$(git -C "$SRC" rev-parse HEAD)"; printf '{"installed_at_unix":%s,"repository":"%s","ref":"%s","source_revision":"%s","daemon_sha256":"%s","guardian_sha256":"%s","code_gate_sha256":"%s","owner_class":"USER_EVIDENCE","origin_class":"ANDROID_TERMUX_DEVICE"}\n' "$(date +%s)" "$REPO" "$REF" "$REV" "$(sha "$BIN/centinal26_daemon.py")" "$(sha "$BIN/centinal26_guardian.py")" "$(sha "$BIN/centinal26_code_gate.py")" > "$STATE/install_manifest.json.tmp"; mv "$STATE/install_manifest.json.tmp" "$STATE/install_manifest.json"; chmod 600 "$STATE/install_manifest.json"; fi
say "[9/9] complete"
if [[ "$DRY" != "1" ]]; then say "CENTINAL26_AUTOPILOT_INSTALL=PASS"; say "source_revision=$(git -C "$SRC" rev-parse HEAD)"; say "home=$ROOT"; say "code_gate=$BIN/code-gate"; say "daemon=$BIN/centinal26_daemon_service.sh"; say "guardian=$BIN/centinal26_guardian_service.sh"; say "policy=$POLICY"; say "Physical device-tested promotion still requires independent device-origin verification."; fi
