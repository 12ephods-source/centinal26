#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
python "$APP_DIR/transcribe.py" --help >/dev/null
python -m py_compile "$APP_DIR/transcribe.py"
python -m unittest -v "$APP_DIR/tests/test_transcriber.py"
bash -n "$APP_DIR/setup.sh" "$APP_DIR/run.sh" "$APP_DIR/device_run.sh" "$APP_DIR/test.sh"
echo 'LOCAL TEST PASS'
