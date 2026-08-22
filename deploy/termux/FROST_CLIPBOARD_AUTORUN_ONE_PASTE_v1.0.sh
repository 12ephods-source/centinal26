#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

REPO="12ephods-source/centinal26"
REF="${FROST_CLIPBOARD_AUTORUN_REF:-main}"
RAW="https://raw.githubusercontent.com/${REPO}/${REF}/automation/device/clipboard_autorun.py"
ROOT="${HOME}/.local/share/frost-clipboard-autorun"
TASKER_DIR="${HOME}/.termux/tasker"
RECEIVER="${ROOT}/clipboard_autorun.py"
STAGE_WRAPPER="${TASKER_DIR}/frost_clipboard_stage"
RUN_WRAPPER="${TASKER_DIR}/frost_clipboard_run"
SETUP_NOTE="${ROOT}/ANDROID_TRIGGER_SETUP.txt"

if [ -z "${PREFIX:-}" ] || [[ "${PREFIX}" != *com.termux* ]]; then
  printf 'ERROR: run this installer inside Termux on Android.\n' >&2
  exit 2
fi

pkg update -y
pkg install -y python curl coreutils
mkdir -p "${ROOT}" "${TASKER_DIR}"
chmod 700 "${ROOT}" "${TASKER_DIR}"

curl -fL --retry 3 --retry-delay 2 "${RAW}" -o "${RECEIVER}.tmp"
python -m py_compile "${RECEIVER}.tmp"
mv "${RECEIVER}.tmp" "${RECEIVER}"
chmod 700 "${RECEIVER}"

cat > "${STAGE_WRAPPER}" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
export FROST_CLIPBOARD_STATE_ROOT=${ROOT@Q}
exec python ${RECEIVER@Q} --stage
EOF
chmod 700 "${STAGE_WRAPPER}"

cat > "${RUN_WRAPPER}" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
export FROST_CLIPBOARD_STATE_ROOT=${ROOT@Q}
exec python ${RECEIVER@Q} --run-pending
EOF
chmod 700 "${RUN_WRAPPER}"

cat > "${SETUP_NOTE}" <<'EOF'
FROST CLIPBOARD -> TERMUX AUTORUN
================================

ANDROID TRIGGER — ONE-TIME SETUP

Required apps:
- Tasker
- Termux:Tasker from the same Termux distribution/signing source as Termux

1. Android Settings -> Apps -> Tasker -> Permissions -> Additional permissions
   Grant: Run commands in Termux environment.

2. In Tasker create a Profile:
   Event -> Clipboard Changed
   Enable "Ignore Set By Tasker" if available.
   Optional event condition: %cl_text matches *# FROST-AUTORUN:1*

3. Attach a Task containing TWO Termux:Tasker actions in this order.

   A1 — STAGE COPIED SCRIPT (BACKGROUND)
   Plugin -> Termux:Tasker
   Executable: frost_clipboard_stage
   Arguments: leave empty
   Working directory: leave empty
   Stdin: %cl_text
   Execute in a terminal session: OFF
   Wait for result: ON

   A2 — OPEN TERMUX + RUN STAGED SCRIPT (FOREGROUND)
   Plugin -> Termux:Tasker
   Executable: frost_clipboard_run
   Arguments: leave empty
   Working directory: leave empty
   Stdin: leave empty
   Execute in a terminal session: ON
   Condition / If: %stdout matches *FROST_AUTORUN_STAGED*

Why two actions: Termux:Tasker stdin is a background-command transport. The first
action receives the clipboard safely and stages exact bytes; the second has no
stdin and can therefore open a visible Termux terminal session to execute the
already-hashed staged script.

4. If Android prevents the foreground Termux session from opening automatically,
   grant Termux "Draw over other apps". Without it, Android 10+ may require a tap
   on the Termux notification before a foreground terminal session can open.

5. On recent Android versions, Clipboard Changed background monitoring may require
   Tasker's ADB-WiFi/Shizuku clipboard workaround (or root/default-IME equivalent).
   Android deliberately blocks ordinary background clipboard reads.

AUTORUN FORMAT

Only clipboard text explicitly marked with the first meaningful line below runs:

# FROST-AUTORUN:1
printf 'hello from copied script\n'

Python:

# FROST-AUTORUN:1 shell=python
print('hello from copied Python')

ChatGPT Markdown code fences are accepted; the fence is removed before execution.
Normal copied text, URLs, passwords, prose, or code without the marker are ignored.

STATE

Exact copied clipboard payloads and normalized scripts:
  ~/.local/share/frost-clipboard-autorun/inbox/
Execution logs and JSON receipts:
  ~/.local/share/frost-clipboard-autorun/runs/
Pending stage transaction:
  ~/.local/share/frost-clipboard-autorun/pending.json
EOF
chmod 600 "${SETUP_NOTE}"

printf '# FROST-AUTORUN:1\nprintf "FROST_CLIPBOARD_AUTORUN_SELF_TEST_PASS\\n"\n' \
  | "${STAGE_WRAPPER}" > "${ROOT}/stage_self_test.out"
grep -q 'FROST_AUTORUN_STAGED' "${ROOT}/stage_self_test.out"
"${RUN_WRAPPER}" > "${ROOT}/run_self_test.out"
grep -q 'FROST_CLIPBOARD_AUTORUN_SELF_TEST_PASS' "${ROOT}/run_self_test.out"

printf 'ordinary clipboard text\n' | "${STAGE_WRAPPER}" > "${ROOT}/ignore_test.out"
grep -q 'FROST_AUTORUN_IGNORED' "${ROOT}/ignore_test.out"

printf '\nINSTALLED:\n  %s\n  %s\n' "${STAGE_WRAPPER}" "${RUN_WRAPPER}"
printf 'TERMUX SELF TEST: PASS\n'
printf 'ANDROID TRIGGER SETUP: %s\n\n' "${SETUP_NOTE}"
printf 'After the one-time Android trigger is configured: copy a marked script -> Tasker stages it -> Termux opens -> the exact staged script runs.\n'
