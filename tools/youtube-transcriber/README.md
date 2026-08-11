# YouTube Transcriber for Android/Termux v1.4.0

Single-purpose, local-first YouTube transcription:

`YouTube URL -> captions -> caption API fallbacks -> whisper.cpp -> English translation when needed -> validated artifacts`

No Gemini, Ollama, channel monitoring, cron, profiling, or security tooling.

## One-touch Termux execution

```bash
chmod +x device_run.sh
./device_run.sh "https://youtu.be/tr9AqDYxFI4?si=MFmYG-GJh1iEMz8c"
```

The device runner installs pinned GitHub-sourced dependencies, builds `whisper.cpp`, downloads the multilingual `base` model, executes the real video, validates all seven required artifacts, hashes them, writes `DEVICE_VALIDATION_REPORT.json`, and best-effort copies the result to Android Downloads.

## Retrieval/fallback chain

1. yt-dlp metadata and creator/automatic captions.
2. `youtube-transcript-api` direct caption fallback.
3. TeamPiped public subtitle fallback (`/streams/{videoId}`).
4. Optional Invidious caption fallback when an API-enabled instance exists.
5. Audio download + FFmpeg 16-kHz mono PCM conversion + `whisper.cpp`.
6. For non-English speech, `whisper.cpp` translation to English.
7. yt-dlp uses Node.js for current YouTube EJS challenges and retries with `web_safari` client when useful.
8. On the Termux device, if the complete normal run fails, `device_run.sh` installs the pinned BgUtils PO-token provider from GitHub tag `1.3.1`, compiles its Node provider, and retries once.

## GitHub role

GitHub is the source-control, CI, and evidence layer for this package. Real-video tests on GitHub-hosted Ubuntu, macOS, and Windows runners confirmed that YouTube currently blocks those cloud egress IPs for this target, so GitHub-hosted Actions are **not** treated as the production transcription worker. The production worker is Android/Termux on the device network.

## Output contract

```text
output/VIDEO_ID/
├── transcript_original.txt
├── transcript_english.txt
├── transcript.srt
├── transcript.vtt
├── transcript.json
├── metadata.json
└── validation_report.json
```

Additional device evidence:

```text
DEVICE_VALIDATION_REPORT.json
device_run.log
```

## Reusable operation

After setup:

```bash
./run.sh "YOUTUBE_URL"
./run.sh "YOUTUBE_URL" --force-whisper
./run.sh "YOUTUBE_URL" --keep-audio
```

## Validation semantics

`validation_report.json` reports `PASS`, `REVIEW`, or `FAIL` from observed transcript structure, timestamp behavior, coverage, repetition, and Whisper token probabilities where available. This is automated validation, not a human ground-truth WER measurement.

`DEVICE_VALIDATION_REPORT.json` separately proves whether the actual Android/Termux execution produced all seven required non-empty artifacts and records SHA-256 hashes.

## Evidence state of this package

Host validation covers Python compilation, shell syntax, 12 unit tests, caption/Piped/Invidious fallback logic, and the seven-file output contract. Authenticated GitHub Actions was also used for real-network testing of `tr9AqDYxFI4`; those cloud runners were blocked by YouTube before captions/audio could be acquired. The actual target is therefore **not** labeled as transcribed until the Android/Termux device run completes.

## Cloud-runner evidence (2026-08-11)

GitHub-hosted Ubuntu, macOS, and Windows runners all reached the exact target video but YouTube returned IP/cloud-runner blocking. All 15 currently documented TeamPiped public APIs were also probed from GitHub; none returned the target transcript at that time. This is an external network/access-state result, not a local parser failure. The primary empirical execution target remains Android/Termux on the device network.
