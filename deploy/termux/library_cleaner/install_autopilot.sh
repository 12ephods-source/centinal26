#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

APP="$HOME/.local/share/frost-library-cleaner"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$APP"
install -m 0644 "$SOURCE_DIR/autopilot_cycle.py" "$APP/autopilot_cycle.py"
python -m py_compile "$APP/autopilot_cycle.py"

echo "Installed Frost Forge Library Cleaner autopilot cycle."
echo "Running bounded improvement loop (maximum 3 cycles)."
python "$APP/autopilot_cycle.py" autopilot --cycles 3
