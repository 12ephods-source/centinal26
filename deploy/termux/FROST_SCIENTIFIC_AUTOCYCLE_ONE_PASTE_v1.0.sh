#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

REPO="12ephods-source/centinal26"
REF="${FROST_SCIENTIFIC_AUTOCYCLE_REF:-main}"
RAW="https://raw.githubusercontent.com/${REPO}/${REF}/automation/device/scientific_autocycle.py"
ROOT="${HOME}/.local/share/frost-scientific-autocycle"
TASKER_DIR="${HOME}/.termux/tasker"
CONFIG_DIR="${HOME}/.config/frost"
CONTROLLER="${ROOT}/scientific_autocycle.py"
STAGE="${TASKER_DIR}/frost_scientific_cycle_stage"
RUN="${TASKER_DIR}/frost_scientific_cycle_run"
REGISTRY="${CONFIG_DIR}/autocycle_agents.json"
SETUP_NOTE="${ROOT}/ANDROID_TRIGGER_SETUP.txt"

if [ -z "${PREFIX:-}" ] || [[ "${PREFIX}" != *com.termux* ]]; then
  printf 'ERROR: run inside Termux on Android.\n' >&2
  exit 2
fi

pkg update -y
pkg install -y python curl coreutils git
mkdir -p "${ROOT}" "${TASKER_DIR}" "${CONFIG_DIR}"
chmod 700 "${ROOT}" "${TASKER_DIR}" "${CONFIG_DIR}"

curl -fL --retry 3 --retry-delay 2 "${RAW}" -o "${CONTROLLER}.tmp"
python -m py_compile "${CONTROLLER}.tmp"
mv "${CONTROLLER}.tmp" "${CONTROLLER}"
chmod 700 "${CONTROLLER}"

cat > "${STAGE}" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
exec python ${CONTROLLER@Q} --stage-stdin --root ${ROOT@Q}
EOF
chmod 700 "${STAGE}"

cat > "${RUN}" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
exec python ${CONTROLLER@Q} --run-pending --root ${ROOT@Q}
EOF
chmod 700 "${RUN}"

if [ ! -e "${REGISTRY}" ]; then
  python - "${REGISTRY}" <<'PY'
import json, os, shutil, sys
from pathlib import Path
registry = {}
if shutil.which("aider"):
    registry["aider"] = {
        "mode": "edit",
        "argv": ["aider", "--yes-always", "--no-git", "--message", "{prompt}", "{candidate}"],
    }
model = os.environ.get("FROST_LLAMA_MODEL")
if model and shutil.which("llama-cli"):
    registry["local-llama"] = {
        "mode": "critique",
        "argv": ["llama-cli", "-m", model, "-p", "{prompt}", "-n", "512"],
    }
path = Path(sys.argv[1])
path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(path, 0o600)
PY
fi

cat > "${SETUP_NOTE}" <<'EOF'
FROST SCIENTIFIC AUTOCYCLE — ANDROID TRIGGER
=============================================

Requires Tasker + Termux:Tasker from a compatible Termux signing source.

Create a Tasker Clipboard Changed profile for clipboard text containing the exact
first meaningful marker `# FROST-AUTORUN:2`.

A1 — BACKGROUND STAGE
  Termux:Tasker executable: frost_scientific_cycle_stage
  stdin: %cl_text
  terminal session: OFF
  wait for result: ON

A2 — FOREGROUND SCIENTIFIC CYCLE
  Termux:Tasker executable: frost_scientific_cycle_run
  stdin: empty
  terminal session: ON
  condition: A1 stdout contains FROST_AUTOCYCLE_STAGED

Android clipboard/background-launch restrictions remain OS-enforced. Recent Android
versions may require Tasker's documented ADB-WiFi/Shizuku clipboard workaround and
Termux may require Draw Over Other Apps to open a foreground terminal automatically.

Example:
# FROST-AUTORUN:2 shell=python
# FROST-CYCLE: {"goal":"emit verified pass","success":{"exit_code":0,"required_text":["AUTOCYCLE_PASS"]},"agent_providers":["deterministic"]}
print("AUTOCYCLE_PASS")
EOF
chmod 600 "${SETUP_NOTE}"

SELF_TEST_INPUT='# FROST-AUTORUN:2 shell=python
# FROST-CYCLE: {"goal":"emit verified pass","success":{"exit_code":0,"required_text":["AUTOCYCLE_PASS"]},"limits":{"max_iterations":2,"episode_timeout_seconds":10},"agent_providers":["deterministic"]}
print("AUTOCYCLE_PASS")'
printf '%s\n' "${SELF_TEST_INPUT}" | "${STAGE}" > "${ROOT}/stage_self_test.out"
grep -q 'FROST_AUTOCYCLE_STAGED' "${ROOT}/stage_self_test.out"
set +e
"${RUN}" > "${ROOT}/run_self_test.out" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ]
grep -q 'GOAL_VERIFIED' "${ROOT}/run_self_test.out"
grep -q 'FROST_AUTOCYCLE_REPORT_READY' "${ROOT}/run_self_test.out"

printf 'INSTALLED: %s\n' "${CONTROLLER}"
printf 'TASKER STAGE: %s\n' "${STAGE}"
printf 'TASKER RUN: %s\n' "${RUN}"
printf 'LOCAL AGENT REGISTRY: %s\n' "${REGISTRY}"
printf 'TERMUX SELF TEST: PASS\n'
printf 'ANDROID SETUP: %s\n' "${SETUP_NOTE}"
