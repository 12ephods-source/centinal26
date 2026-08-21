#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

APP="$HOME/.local/share/frost-library-cleaner"
SERVICE="$PREFIX/var/service/frost-library-cleaner"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[1/5] Installing dependencies"
pkg install -y python android-tools termux-services coreutils >/dev/null

mkdir -p "$APP" "$SERVICE/log" "$HOME/.termux/boot"
install -m 0644 "$SOURCE_DIR/frost_library_cleanerd.py" "$APP/frost_library_cleanerd.py"
install -m 0644 "$SOURCE_DIR/package_evidence.py" "$APP/package_evidence.py"

if [ ! -e "$HOME/storage/downloads" ]; then
  termux-setup-storage || true
fi
mkdir -p "$HOME/storage/downloads/FrostForgeLibraryArchive" || true
mkdir -p "$HOME/storage/downloads/FrostForgeLibraryCleanerEvidence" || true

echo "[2/5] Installing runit service"
cat > "$SERVICE/run" <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
exec 2>&1
exec python "$HOME/.local/share/frost-library-cleaner/frost_library_cleanerd.py" daemon
EOF
chmod 0755 "$SERVICE/run"

cat > "$SERVICE/log/run" <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
mkdir -p "$HOME/.local/share/frost-library-cleaner/service-log"
exec svlogd -tt "$HOME/.local/share/frost-library-cleaner/service-log"
EOF
chmod 0755 "$SERVICE/log/run"

echo "[3/5] Installing boot hook"
cat > "$HOME/.termux/boot/frost-library-cleaner" <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock >/dev/null 2>&1 || true
sv up "$PREFIX/var/service/frost-library-cleaner" >/dev/null 2>&1 || true
EOF
chmod 0755 "$HOME/.termux/boot/frost-library-cleaner"

echo "[4/5] Initializing configuration"
python "$APP/frost_library_cleanerd.py" setup || true

echo "[5/5] Starting service"
sv up "$SERVICE" >/dev/null 2>&1 || true

cat <<'EOF'
Installed Frost Forge Library Cleaner.

Before automatic deletion, run:
  python ~/.local/share/frost-library-cleaner/frost_library_cleanerd.py dry-run

If ADB is not connected, enable Android Wireless debugging and pair once:
  adb pair <host:pair-port>

Useful commands:
  python ~/.local/share/frost-library-cleaner/frost_library_cleanerd.py status
  python ~/.local/share/frost-library-cleaner/frost_library_cleanerd.py once
  python ~/.local/share/frost-library-cleaner/package_evidence.py
  sv down "$PREFIX/var/service/frost-library-cleaner"
  sv up "$PREFIX/var/service/frost-library-cleaner"
EOF
