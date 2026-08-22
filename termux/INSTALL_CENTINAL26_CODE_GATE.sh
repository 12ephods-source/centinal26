#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
umask 077
ROOT="${CENTINAL26_HOME:-$HOME/.centinal26}"
BIN="$ROOT/bin"; SRC="$ROOT/src/centinal26"
mkdir -p "$BIN" "$ROOT/code_inbox" "$ROOT/evidence/code_gate" "$ROOT/reports/code_gate"
[[ "${PREFIX:-}" == *com.termux* ]] || { echo 'Run in Termux' >&2; exit 2; }
pkg install -y python coreutils >/dev/null
if [[ ! -d "$SRC/.git" ]]; then
  git clone --branch feature/termux-persistent-daemon-v1 --single-branch https://github.com/12ephods-source/centinal26.git "$SRC"
else
  git -C "$SRC" fetch --prune origin feature/termux-persistent-daemon-v1
  git -C "$SRC" checkout -B feature/termux-persistent-daemon-v1 origin/feature/termux-persistent-daemon-v1
fi
python -m py_compile "$SRC/termux/centinal26_code_gate.py"
install -m 700 "$SRC/termux/centinal26_code_gate.py" "$BIN/centinal26-code-gate"
cat > "$BIN/code-gate" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
exec python "$BIN/centinal26-code-gate" "\$@"
EOF
chmod 700 "$BIN/code-gate"
"$BIN/code-gate" --help >/dev/null
printf 'CENTINAL26_CODE_GATE_INSTALL=PASS\ncommand=%s\n' "$BIN/code-gate"
