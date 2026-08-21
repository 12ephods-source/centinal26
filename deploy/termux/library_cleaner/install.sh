#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

APP="$HOME/.local/share/frost-library-cleaner"
SERVICE="$PREFIX/var/service/frost-library-cleaner"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[1/6] Installing dependencies"
pkg install -y python android-tools termux-services coreutils >/dev/null

mkdir -p "$APP" "$SERVICE/log" "$HOME/.termux/boot"
install -m 0644 "$SOURCE_DIR/frost_library_cleanerd.py" "$APP/frost_library_cleanerd.py"
install -m 0644 "$SOURCE_DIR/package_evidence.py" "$APP/package_evidence.py"

if [ ! -e "$HOME/storage/downloads" ]; then
  termux-setup-storage || true
fi
mkdir -p "$HOME/storage/downloads/FrostForgeLibraryArchive" || true
mkdir -p "$HOME/storage/downloads/FrostForgeLibraryCleanerEvidence" || true

echo "[2/6] Installing runit service"
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

echo "[3/6] Installing qualification and disarm controls"
cat > "$APP/qualify_and_arm.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
APP="$HOME/.local/share/frost-library-cleaner"
SERVICE="$PREFIX/var/service/frost-library-cleaner"
RESULT="$APP/qualification-result.json"

sv down "$SERVICE" >/dev/null 2>&1 || true
python - <<'PY'
import json
from pathlib import Path
p = Path.home() / ".local/share/frost-library-cleaner/config.json"
config = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
config["auto_delete"] = False
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
PY

if ! python "$APP/frost_library_cleanerd.py" dry-run > "$RESULT"; then
  echo "QUALIFICATION_FAILED: dry-run command failed; automatic deletion remains disabled" >&2
  exit 3
fi

if ! python - "$RESULT" <<'PY'
import json
import sys
from pathlib import Path
result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
raise SystemExit(0 if not result.get("errors") else 1)
PY
then
  echo "QUALIFICATION_FAILED: dry-run reported errors; automatic deletion remains disabled" >&2
  cat "$RESULT" >&2
  exit 3
fi

python - <<'PY'
import json
from pathlib import Path
p = Path.home() / ".local/share/frost-library-cleaner/config.json"
config = json.loads(p.read_text(encoding="utf-8"))
config["auto_delete"] = True
p.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
PY

sv up "$SERVICE" >/dev/null 2>&1 || true
echo "QUALIFICATION_PASS: automatic deletion armed and daemon enabled"
EOF
chmod 0755 "$APP/qualify_and_arm.sh"

cat > "$APP/disarm.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
APP="$HOME/.local/share/frost-library-cleaner"
SERVICE="$PREFIX/var/service/frost-library-cleaner"
sv down "$SERVICE" >/dev/null 2>&1 || true
python - <<'PY'
import json
from pathlib import Path
p = Path.home() / ".local/share/frost-library-cleaner/config.json"
config = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
config["auto_delete"] = False
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
PY
echo "AUTOMATIC_DELETION_DISABLED"
EOF
chmod 0755 "$APP/disarm.sh"

echo "[4/6] Installing boot hook"
cat > "$HOME/.termux/boot/frost-library-cleaner" <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock >/dev/null 2>&1 || true
if python - <<'PY' >/dev/null 2>&1
import json
from pathlib import Path
p = Path.home() / ".local/share/frost-library-cleaner/config.json"
raise SystemExit(0 if p.exists() and json.loads(p.read_text(encoding="utf-8")).get("auto_delete") is True else 1)
PY
then
  sv up "$PREFIX/var/service/frost-library-cleaner" >/dev/null 2>&1 || true
else
  sv down "$PREFIX/var/service/frost-library-cleaner" >/dev/null 2>&1 || true
fi
EOF
chmod 0755 "$HOME/.termux/boot/frost-library-cleaner"

echo "[5/6] Initializing fail-closed configuration"
python "$APP/frost_library_cleanerd.py" setup || true
python - <<'PY'
import json
from pathlib import Path
p = Path.home() / ".local/share/frost-library-cleaner/config.json"
config = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
config["auto_delete"] = False
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
PY
sv down "$SERVICE" >/dev/null 2>&1 || true

echo "[6/6] Running non-destructive qualification"
if "$APP/qualify_and_arm.sh"; then
  echo "Cleaner qualified and armed."
else
  echo "Cleaner installed but remains DISARMED."
  echo "After Android Wireless Debugging and the authenticated Library UI are ready, run:"
  echo "  ~/.local/share/frost-library-cleaner/qualify_and_arm.sh"
fi

cat <<'EOF'
Installed Frost Forge Library Cleaner.

The installer always starts fail-closed. Automatic deletion is armed only after a
non-destructive UI dry-run completes with zero reported errors.

If ADB is not connected, enable Android Wireless debugging and pair once:
  adb pair <host:pair-port>

Useful commands:
  ~/.local/share/frost-library-cleaner/qualify_and_arm.sh
  ~/.local/share/frost-library-cleaner/disarm.sh
  python ~/.local/share/frost-library-cleaner/frost_library_cleanerd.py dry-run
  python ~/.local/share/frost-library-cleaner/frost_library_cleanerd.py status
  python ~/.local/share/frost-library-cleaner/frost_library_cleanerd.py once
  python ~/.local/share/frost-library-cleaner/package_evidence.py
  sv down "$PREFIX/var/service/frost-library-cleaner"
  sv up "$PREFIX/var/service/frost-library-cleaner"
EOF
