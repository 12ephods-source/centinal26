#!/data/data/com.termux/files/usr/bin/bash
# One-touch real-device install + transcription + evidence report.
set -Eeuo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="${1:-https://youtu.be/tr9AqDYxFI4?si=MFmYG-GJh1iEMz8c}"
VID=""
LOG="$APP_DIR/device_run.log"
REPORT="$APP_DIR/DEVICE_VALIDATION_REPORT.json"
mkdir -p "$APP_DIR"
exec > >(tee -a "$LOG") 2>&1

printf '== YouTube Transcriber DEVICE RUN v1.4.0 ==\nTarget: %s\nStarted: %s\n' "$TARGET" "$(date -Iseconds)"

bash "$APP_DIR/setup.sh"
VID="$(APP_DIR="$APP_DIR" TARGET="$TARGET" python - <<'PYVID'
import os, sys
sys.path.insert(0, os.environ["APP_DIR"])
import transcribe
print(transcribe.extract_video_id(os.environ["TARGET"]))
PYVID
)"

run_once() {
  "$APP_DIR/run.sh" "$TARGET"
}

set +e
run_once
rc=$?
set -e

# Current YouTube PO-token enforcement can produce 403/bot-check failures.
# Only if the normal pipeline fails, install the upstream-recommended featured
# provider stack and retry. This remains local/free and does not add an AI API.
if [[ $rc -ne 0 ]]; then
  echo "Primary run failed (rc=$rc). Applying PO-token mitigation and retrying..."
  pkg install -y libvips xorgproto nodejs git
  mkdir -p "$HOME/.gyp"
  printf "{'variables':{'android_ndk_path':''}}\n" > "$HOME/.gyp/include.gypi"
  POT_VER="${POT_PROVIDER_VERSION:-1.3.1}"
  # Install the Python plugin from the pinned GitHub tag rather than PyPI.
  python -m pip install -U "git+https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git@${POT_VER}"
  POT_HOME="$HOME/bgutil-ytdlp-pot-provider"
  rm -rf "$POT_HOME.tmp"
  if [[ ! -d "$POT_HOME/.git" ]]; then
    git clone --depth 1 --branch "$POT_VER" https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git "$POT_HOME.tmp"
    rm -rf "$POT_HOME"
    mv "$POT_HOME.tmp" "$POT_HOME"
  else
    git -C "$POT_HOME" fetch --depth 1 origin "refs/tags/$POT_VER:refs/tags/$POT_VER" || true
    git -C "$POT_HOME" checkout -f "$POT_VER" || true
  fi
  (cd "$POT_HOME/server" && npm ci && npx tsc)
  set +e
  run_once
  rc=$?
  set -e
fi

OUT="$APP_DIR/output/$VID"
if [[ ! -d "$OUT" ]]; then
  # run.sh defaults output under package directory; preserve future renamed target IDs.
  OUT="$(find "$APP_DIR/output" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2- || true)"
fi

python - "$OUT" "$REPORT" "$TARGET" "$rc" <<'PY'
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
out = Path(sys.argv[1]) if sys.argv[1] else Path('/nonexistent')
report = Path(sys.argv[2])
target = sys.argv[3]
rc = int(sys.argv[4])
required = [
    'transcript_original.txt','transcript_english.txt','transcript.srt',
    'transcript.vtt','transcript.json','metadata.json','validation_report.json'
]
files = {}
missing = []
for name in required:
    p = out / name
    if p.is_file() and p.stat().st_size > 0:
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        files[name] = {'bytes': p.stat().st_size, 'sha256': h}
    else:
        missing.append(name)
validation = None
vp = out / 'validation_report.json'
if vp.is_file():
    try: validation = json.loads(vp.read_text(encoding='utf-8')).get('status')
    except Exception: validation = 'UNREADABLE'
pipeline = 'PASS' if rc == 0 and not missing else 'FAIL'
obj = {
    'device_pipeline_status': pipeline,
    'transcript_validation_status': validation,
    'target': target,
    'output_directory': str(out),
    'required_files': required,
    'missing_or_empty': missing,
    'files': files,
    'run_exit_code': rc,
    'generated_at': datetime.now(timezone.utc).isoformat(),
}
report.write_text(json.dumps(obj, indent=2) + '\n', encoding='utf-8')
print(json.dumps(obj, indent=2))
if pipeline != 'PASS':
    raise SystemExit(31)
PY

# Best-effort copy to Android Downloads.
if [[ -d "$HOME/storage/downloads" && -w "$HOME/storage/downloads" ]]; then
  DEST="$HOME/storage/downloads/youtube-transcriber-$VID"
  rm -rf "$DEST"
  cp -a "$OUT" "$DEST"
  cp "$REPORT" "$DEST/DEVICE_VALIDATION_REPORT.json"
  echo "Shared copy: $DEST"
fi

echo
echo "== TRANSCRIPT PREVIEW =="
sed -n '1,30p' "$OUT/transcript_original.txt"
echo
echo "DEVICE PIPELINE: PASS"
echo "Output: $OUT"
echo "Report: $REPORT"
echo "Log: $LOG"
