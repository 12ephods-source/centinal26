#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$HOME/.local/share/youtube-transcriber"
WHISPER_DIR="$DATA_DIR/whisper.cpp"
MODEL_DIR="$DATA_DIR/models"
MODEL="${WHISPER_MODEL_NAME:-base}"
JOBS="${TRANSCRIBER_BUILD_JOBS:-2}"

# Pinned, verified upstream versions. Update deliberately rather than silently.
YTDLP_VERSION="${YTDLP_VERSION:-2026.07.04}"
YTDLP_SHA256="${YTDLP_SHA256:-495be29ff4d9d4e9be7eabdfef225221e5d5282e77f2f505abc6dca80349f3fd}"
WHISPER_CPP_REF="${WHISPER_CPP_REF:-v1.9.2}"
YTA_REF="${YTA_REF:-v1.2.4}"

printf '== YouTube Transcriber v1.4.0 setup (GitHub-first) ==\n'
command -v pkg >/dev/null 2>&1 || { echo 'ERROR: setup.sh must run inside Termux.' >&2; exit 1; }

pkg update -y
pkg install -y python python-pip ffmpeg git cmake clang make nodejs curl openssl ca-certificates coreutils

NODE_MAJOR="$(node -p 'process.versions.node.split(`.`)[0]' 2>/dev/null || echo 0)"
if (( NODE_MAJOR < 22 )); then
  echo "ERROR: yt-dlp EJS requires Node >=22; found $(node --version 2>/dev/null || echo none)" >&2
  exit 12
fi

# Install the official GitHub zipimport executable. Upstream bundles yt-dlp-ejs
# in this artifact, so no PyPI yt-dlp package is required.
YTDLP_URL="https://github.com/yt-dlp/yt-dlp/releases/download/${YTDLP_VERSION}/yt-dlp"
TMP_YTDLP="$(mktemp)"
trap 'rm -f "$TMP_YTDLP"' EXIT
curl -fL --retry 3 --retry-delay 2 "$YTDLP_URL" -o "$TMP_YTDLP"
printf '%s  %s\n' "$YTDLP_SHA256" "$TMP_YTDLP" | sha256sum -c -
cp "$TMP_YTDLP" "$PREFIX/bin/yt-dlp"
chmod 0755 "$PREFIX/bin/yt-dlp"

# Secondary direct-caption implementation, sourced from a pinned GitHub tag.
python -m pip install --upgrade pip wheel setuptools
python -m pip install --upgrade "git+https://github.com/jdepoix/youtube-transcript-api.git@${YTA_REF}"

mkdir -p "$DATA_DIR" "$MODEL_DIR"
if [[ ! -d "$WHISPER_DIR/.git" ]]; then
  git clone --depth 1 --branch "$WHISPER_CPP_REF" https://github.com/ggml-org/whisper.cpp.git "$WHISPER_DIR"
else
  git -C "$WHISPER_DIR" fetch --depth 1 origin "refs/tags/$WHISPER_CPP_REF:refs/tags/$WHISPER_CPP_REF" || true
  git -C "$WHISPER_DIR" checkout -f "$WHISPER_CPP_REF"
fi

cmake -S "$WHISPER_DIR" -B "$WHISPER_DIR/build" \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_NATIVE=OFF \
  -DGGML_VULKAN=OFF
cmake --build "$WHISPER_DIR/build" -j"$JOBS"

MODEL_PATH="$MODEL_DIR/ggml-${MODEL}.bin"
if [[ ! -s "$MODEL_PATH" ]]; then
  "$WHISPER_DIR/models/download-ggml-model.sh" "$MODEL" "$MODEL_DIR"
fi

CLI="$WHISPER_DIR/build/bin/whisper-cli"
[[ -x "$CLI" ]] || { echo "ERROR: whisper-cli not built at $CLI" >&2; exit 1; }
[[ -s "$MODEL_PATH" ]] || { echo "ERROR: model not found at $MODEL_PATH" >&2; exit 1; }

cat > "$APP_DIR/.env" <<ENVEOF
WHISPER_CPP_DIR=$WHISPER_DIR
WHISPER_MODEL=$MODEL_PATH
ENVEOF

chmod +x "$APP_DIR/run.sh" "$APP_DIR/transcribe.py" "$APP_DIR/device_run.sh" "$APP_DIR/test.sh" 2>/dev/null || true
python "$APP_DIR/transcribe.py" --help >/dev/null
printf 'yt-dlp: '; yt-dlp --version
printf 'node: '; node --version
printf 'whisper.cpp ref: %s\n' "$WHISPER_CPP_REF"
ffmpeg -version | head -n 1
printf '\nSETUP PASS\n'
