#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

REPO="12ephods-source/centinal26"
REF="${FROST_CLIPBOARD_AUTORUN_REF:-main}"
RAW="https://raw.githubusercontent.com/${REPO}/${REF}/automation/device/clipboard_autorun.py"
ROOT="${HOME}/.local/share/frost-clipboard-autorun"
TASKER_DIR="${HOME}/.termux/tasker"
RECEIVER="${ROOT}/clipboard_autorun.py"
WRAPPER="${TASKER_DIR}/frost_clipboard_autorun"
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

cat > "${WRAPPER}" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
export FROST_CLIPBOARD_STATE_ROOT=${ROOT@Q}
exec python ${RECEIVER@Q}
EOF
chmod 700 "${WRAPPER}"

cat > "${SETUP_NOTE}" <<'EOF'
FROST CLIPBOARD -> TERMUX AUTORUN
================================

ANDROID TRIGGER (one-time setup)

Required apps:
- Tasker
- Termux:Tasker from the same Termux distribution/signing source as Termux

1. Android Settings -> Apps -> Tasker -> Permissions -> Additional permissions
   Grant: Run commands in Termux environment.

2. In Tasker create a Profile:
   Event -> Clipboard Changed
   Enable "Ignore Set By Tasker" if available.

3. Attach a Task with:
   Plugin -> Termux:Tasker
   Executable: frost_clipboard_autorun
   Arguments: leave empty
   Working directory: leave empty
   Stdin: %cl_text
   Execute in a terminal session: ON
   Wait for result: optional

4. If Android prevents the foreground Termux session from opening automatically,
   grant Termux "Draw over other apps". Background execution does not need this,
   but foreground terminal-session launch can.

5. On recent Android versions, Clipboard Changed background monitoring may require
   Tasker's ADB-WiFi/Shizuku clipboard workaround (or another privileged clipboard
   trigger). Android deliberately blocks normal background clipboard reads.

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

Exact copied scripts:
  ~/.local/share/frost-clipboard-autorun/inbox/
Execution logs and JSON receipts:
  ~/.local/share/frost-clipboard-autorun/runs/
EOF
chmod 600 "${SETUP_NOTE}"

printf '# FROST-AUTORUN:1\nprintf "FROST_CLIPBOARD_AUTORUN_SELF_TEST_PASS\\n"\n' \
  | "${WRAPPER}" > "${ROOT}/self_test.out"
grep -q 'FROST_CLIPBOARD_AUTORUN_SELF_TEST_PASS' "${ROOT}/self_test.out"

printf 'ordinary clipboard text\n' | "${WRAPPER}" > "${ROOT}/ignore_test.out"
grep -q '"status": "IGNORED"' "${ROOT}/ignore_test.out"

printf '\nINSTALLED: %s\n' "${WRAPPER}"
printf 'SELF TEST: PASS\n'
printf 'ANDROID TRIGGER SETUP: %s\n\n' "${SETUP_NOTE}"
printf 'After the one-time Tasker trigger is configured, copying a marked script sends it to a Termux terminal session and runs it automatically.\n'
