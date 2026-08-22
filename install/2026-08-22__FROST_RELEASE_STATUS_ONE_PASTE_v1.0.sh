#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

REPO="${CENTINAL26_ROOT:-$HOME/centinal26}"
STATE="${FROST_PERSISTENT_STATE:-$HOME/.frost_persistent_v4}/project_state.json"
PROFILE="$REPO/automation/persistent/release_profile.py"

[[ -f "$STATE" ]] || { echo '{"error":"missing_project_state"}'; exit 2; }
[[ -f "$PROFILE" ]] || { echo '{"error":"missing_release_profile"}'; exit 2; }

python - "$STATE" "$PROFILE" <<'PY'
import importlib.util
import json
import pathlib
import sys

state = pathlib.Path(sys.argv[1])
module_path = pathlib.Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("release_profile", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(json.dumps(module.evaluate_state_file(state), indent=2, sort_keys=True))
PY
