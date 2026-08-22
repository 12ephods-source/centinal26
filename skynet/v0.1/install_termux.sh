#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/.skynet"
BIN="$HOME/.local/bin"
mkdir -p "$APP" "$BIN" "$HOME/.termux/boot"
if command -v pkg >/dev/null 2>&1; then
  pkg update -y || true
  pkg install -y python git || true
fi
install -m 700 "$HERE/skynet_core.py" "$BIN/skynet"
"$BIN/skynet" init >/dev/null
cat > "$APP/worker.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
while true; do
  "$HOME/.local/bin/skynet" work-once >> "$HOME/.skynet/worker.log" 2>&1 || true
  sleep 60
done
EOF
chmod 700 "$APP/worker.sh"
cat > "$HOME/.termux/boot/skynet.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock >/dev/null 2>&1 || true
pgrep -f "$HOME/.skynet/worker.sh" >/dev/null 2>&1 || nohup "$HOME/.skynet/worker.sh" >/dev/null 2>&1 &
EOF
chmod 700 "$HOME/.termux/boot/skynet.sh"
printf 'SKY NET installed. Run: skynet status\n'
