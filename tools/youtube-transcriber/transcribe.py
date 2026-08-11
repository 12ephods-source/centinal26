#!/usr/bin/env python3
"""Pure local-first YouTube transcriber for Android/Termux."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen

SCHEMA_VERSION = "1.4"
PIPED_INSTANCES = (
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.leptons.xyz",
    "https://pipedapi.nosebs.ru",
    "https://pipedapi-libre.kavin.rocks",
    "https://piped-api.privacy.com.de",
    "https://pipedapi.adminforge.de",
    "https://api.piped.yt",
    "https://pipedapi.drgns.space",
    "https://pipedapi.owo.si",
    "https://pipedapi.ducks.party",
    "https://piped-api.codespace.cz",
    "https://pipedapi.reallyaweso.me",
    "https://api.piped.private.coffee",
    "https://pipedapi.darkness.services",
    "https://pipedapi.orangenet.cc",
)
TAG_RE = re.compile(r"<[^>]+>")
TIMING_RE = re.compile(
    r"(?P<s>\d{1,2}:\d{2}(?::\d{2})?[\.,]\d{3})\s+-->\s+"
    r"(?P<e>\d{1,2}:\d{2}(?::\d{2})?[\.,]\d{3})"
)


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def run(cmd: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        check=True,
    )


def require(name: str) -> str:
    p = shutil.which(name)
    if not p:
        raise RuntimeError(f"Required executable not found: {name}")
    return p


def extract_video_id(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"[\w-]{11}", value):
        return value
    u = urlparse(value)
    host = u.netloc.lower()
    vid = ""
    if host in {"youtu.be", "www.youtu.be"}:
        vid = u.path.strip("/").split("/")[0]
    elif "youtube.com" in host:
        if u.path == "/watch":
            vid = parse_qs(u.query).get("v", [""])[0]
        elif u.path.startswith(("/shorts/", "/embed/", "/live/")):
            parts = u.path.strip("/").split("/")
            vid = parts[1] if len(parts) > 1 else ""
    if not re.fullmatch(r"[\w-]{11}", vid):
        raise ValueError("Could not extract an 11-character YouTube video ID")
    return vid


def base_lang(lang: str | None) -> str | None:
    return re.split(r"[-_]", lang.lower(), maxsplit=1)[0] if lang else None


def is_english(lang: str | None) -> bool:
    return base_lang(lang) == "en" or (lang or "").lower() == "english"


def ytdlp_args() -> list[str]:
    return ["--js-runtimes", "node"] if shutil.which("node") else []


def run_ytdlp(exe: str, args: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    attempts = [args, ["--extractor-args", "youtube:player_client=web_safari"] + args]
    last: Exception | None = None
    for n, args2 in enumerate(attempts):
        try:
            return run([exe] + ytdlp_args() + args2, capture=capture)
        except subprocess.CalledProcessError as exc:
            last = exc
            if n == 0:
                print("yt-dlp primary path failed; retrying web_safari", file=sys.stderr)
    assert last
    raise last


def metadata(url: str, ytdlp: str) -> dict[str, Any]:
    p = run_ytdlp(ytdlp, ["--dump-single-json", "--skip-download", "--no-warnings", "--no-playlist", url], capture=True)
    return json.loads(p.stdout)


def select_caption(meta: dict[str, Any]) -> tuple[str, str] | None:
    hint = base_lang(str(meta.get("language") or ""))
    for kind, key in (("human", "subtitles"), ("auto", "automatic_captions")):
        tracks = {k: v for k, v in (meta.get(key) or {}).items() if k != "live_chat" and v}
        for target in (hint, "en"):
            if target:
                for lang in tracks:
                    if base_lang(lang) == target:
                        return kind, lang
        if tracks:
            return kind, sorted(tracks)[0]
    return None


def ts_seconds(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


def fmt_ts(sec: float, *, srt: bool = False) -> str:
    ms = max(0, int(round(float(sec) * 1000)))
    hh, rem = divmod(ms, 3_600_000)
    mm, rem = divmod(rem, 60_000)
    ss, ms = divmod(rem, 1000)
    return f"{hh:02d}:{mm:02d}:{ss:02d}{',' if srt else '.'}{ms:03d}"


def clean_text(text: str) -> str:
    return " ".join(html.unescape(TAG_RE.sub("", text)).split()).strip()


def parse_vtt_text(raw: str) -> list[dict[str, Any]]:
    lines = raw.splitlines()
    out: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        m = TIMING_RE.search(lines[i])
        if not m:
            i += 1
            continue
        start, end = ts_seconds(m.group("s")), ts_seconds(m.group("e"))
        i += 1
        buf: list[str] = []
        while i < len(lines) and lines[i].strip():
            if not TIMING_RE.search(lines[i]):
                buf.append(lines[i])
            i += 1
        text = clean_text(" ".join(buf))
        if text:
            if out and text == out[-1]["text"] and start <= out[-1]["end"] + 0.25:
                out[-1]["end"] = max(out[-1]["end"], end)
            else:
                out.append({"start": start, "end": end, "text": text})
        i += 1
    return out


def write_outputs(segments: list[dict[str, Any]], outdir: Path) -> None:
    (outdir / "transcript_original.txt").write_text("\n".join(s["text"] for s in segments).strip() + "\n", encoding="utf-8")
    srt = []
    vtt = ["WEBVTT\n"]
    for n, s in enumerate(segments, 1):
        srt.append(f"{n}\n{fmt_ts(s['start'], srt=True)} --> {fmt_ts(s['end'], srt=True)}\n{s['text']}\n")
        vtt.append(f"{fmt_ts(s['start'])} --> {fmt_ts(s['end'])}\n{s['text']}\n")
    (outdir / "transcript.srt").write_text("\n".join(srt), encoding="utf-8")
    (outdir / "transcript.vtt").write_text("\n".join(vtt), encoding="utf-8")


def download_ytdlp_caption(url: str, ytdlp: str, outdir: Path, kind: str, lang: str) -> list[dict[str, Any]]:
    for p in outdir.glob("caption*.vtt"):
        p.unlink(missing_ok=True)
    args = ["--skip-download", "--sub-format", "vtt", "--sub-langs", lang,
            "-o", str(outdir / "caption.%(ext)s"),
            "--write-subs" if kind == "human" else "--write-auto-subs", url]
    run_ytdlp(ytdlp, args)
    paths = sorted(outdir.glob("caption*.vtt"))
    if not paths:
        raise RuntimeError("yt-dlp caption file missing")
    raw = paths[-1].read_text(encoding="utf-8", errors="replace")
    for p in paths:
        p.unlink(missing_ok=True)
    segs = parse_vtt_text(raw)
    if not segs:
        raise RuntimeError("caption VTT was empty or unparseable")
    return segs


def caption_api(video_id: str, preferred: list[str]) -> tuple[list[dict[str, Any]], str, str]:
    from youtube_transcript_api import YouTubeTranscriptApi
    transcripts = YouTubeTranscriptApi().list(video_id)
    chosen = None
    for method in ("find_manually_created_transcript", "find_generated_transcript", "find_transcript"):
        try:
            chosen = getattr(transcripts, method)(preferred)
            break
        except Exception:
            pass
    if chosen is None:
        chosen = next(iter(transcripts))
    segs = []
    for x in chosen.fetch():
        text = clean_text(str(x.text))
        if text:
            segs.append({"start": float(x.start), "end": float(x.start) + float(x.duration), "text": text})
    if not segs:
        raise RuntimeError("caption API returned no transcript")
    return segs, ("auto" if getattr(chosen, "is_generated", False) else "human"), str(getattr(chosen, "language_code", "unknown"))


def http_get(url: str, timeout: float = 15.0) -> str:
    req = Request(url, headers={"User-Agent": "YouTubeTranscriber/1.4", "Accept": "application/json,text/vtt,*/*;q=0.1"})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def piped_caption(video_id: str, preferred: list[str]) -> tuple[list[dict[str, Any]], str, str]:
    instances = [x.strip().rstrip("/") for x in os.getenv("PIPED_INSTANCES", ",".join(PIPED_INSTANCES)).split(",") if x.strip()]
    failures = []
    for base in instances:
        try:
            info = json.loads(http_get(f"{base}/streams/{video_id}"))
            tracks = [x for x in (info.get("subtitles") or []) if x.get("url") and x.get("code")]
            def score(x: dict[str, Any]) -> tuple[int, int, int]:
                code = base_lang(str(x.get("code") or ""))
                rank = next((i for i, p in enumerate(preferred) if code == base_lang(p)), 99)
                return rank, 0 if "vtt" in str(x.get("mimeType") or "").lower() else 1, 1 if x.get("autoGenerated") else 0
            for track in sorted(tracks, key=score):
                if track.get("mimeType") and "vtt" not in str(track["mimeType"]).lower():
                    continue
                segs = parse_vtt_text(http_get(urljoin(base + "/", str(track["url"]))))
                if segs:
                    return segs, "piped", str(track.get("code") or "unknown")
            failures.append(f"{base}: no usable subtitle")
        except Exception as exc:
            failures.append(f"{base}: {type(exc).__name__}")
    raise RuntimeError("Piped fallback exhausted: " + "; ".join(failures[-5:]))


def normalize_audio(url: str, ytdlp: str, ffmpeg: str, outdir: Path) -> Path:
    for p in outdir.glob("source_audio.*"):
        p.unlink(missing_ok=True)
    run_ytdlp(ytdlp, ["-f", "bestaudio/best", "-x", "--audio-format", "wav", "--no-playlist",
                       "-o", str(outdir / "source_audio.%(ext)s"), url])
    sources = list(outdir.glob("source_audio.*"))
    if not sources:
        raise RuntimeError("audio download produced no file")
    dest = outdir / "normalized.wav"
    run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(max(sources, key=lambda p: p.stat().st_size)),
         "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dest)])
    if not dest.exists() or dest.stat().st_size < 44:
        raise RuntimeError("normalized WAV missing")
    return dest


def whisper_paths(cli: str | None, model: str | None) -> tuple[str, str]:
    cli_candidates = [cli, shutil.which("whisper-cli"), os.getenv("WHISPER_CPP_DIR") and str(Path(os.environ["WHISPER_CPP_DIR"]) / "build/bin/whisper-cli"),
                      str(Path.home() / ".local/share/youtube-transcriber/whisper.cpp/build/bin/whisper-cli")]
    model_candidates = [model, os.getenv("WHISPER_MODEL"), str(Path.home() / ".local/share/youtube-transcriber/models/ggml-base.bin")]
    c = next((str(Path(x).expanduser()) for x in cli_candidates if x and Path(x).expanduser().exists()), None)
    m = next((str(Path(x).expanduser()) for x in model_candidates if x and Path(x).expanduser().exists()), None)
    if not c or not m:
        raise RuntimeError("whisper.cpp CLI/model missing; run setup.sh")
    return c, m


def whisper(cli: str, model: str, audio: Path, base: Path, *, translate: bool = False) -> tuple[str, dict[str, Any] | None]:
    cmd = [cli, "-m", model, "-f", str(audio), "-l", "auto", "--no-gpu", "-np", "-otxt", "-of", str(base)]
    if translate:
        cmd.append("-tr")
    else:
        cmd += ["-osrt", "-ovtt", "-ojf"]
    run(cmd)
    txt = Path(str(base) + ".txt")
    if not txt.exists() or not txt.read_text(encoding="utf-8", errors="replace").strip():
        raise RuntimeError("whisper.cpp produced no text")
    raw = None
    jp = Path(str(base) + ".json")
    if jp.exists():
        raw = json.loads(jp.read_text(encoding="utf-8"))
    return txt.read_text(encoding="utf-8", errors="replace"), raw


def whisper_segments(raw: dict[str, Any] | None, fallback_text: str, duration: float) -> tuple[list[dict[str, Any]], list[float], str | None]:
    segs, probs = [], []
    lang = None
    if raw:
        lang = str((raw.get("result") or {}).get("language") or "") or None
        for x in raw.get("transcription", []) or []:
            off = x.get("offsets") or {}
            text = clean_text(str(x.get("text") or ""))
            if text:
                segs.append({"start": float(off.get("from", 0)) / 1000, "end": float(off.get("to", 0)) / 1000, "text": text})
            for tok in x.get("tokens", []) or []:
                p = tok.get("p")
                if isinstance(p, (int, float)) and 0 <= p <= 1:
                    probs.append(float(p))
    if not segs:
        segs = [{"start": 0.0, "end": duration, "text": clean_text(fallback_text)}]
    return segs, probs, lang


def validate(segs: list[dict[str, Any]], duration: float | None, probs: list[float], source: str) -> dict[str, Any]:
    errors, warnings = [], []
    if not segs:
        errors.append("no transcript segments")
    for i, s in enumerate(segs):
        if s["end"] < s["start"]:
            errors.append(f"segment {i}: end before start")
        if i and s["start"] < segs[i - 1]["start"] - 0.05:
            errors.append(f"segment {i}: timestamp regression")
    coverage = None
    if duration and duration > 0 and segs:
        coverage = min(1.0, max(float(s["end"]) for s in segs) / duration)
        if coverage < 0.8:
            warnings.append(f"transcript reaches only {coverage:.1%} of video duration")
    confidence: dict[str, Any] = {"available": bool(probs), "method": None}
    if probs:
        confidence.update({"method": "whisper.cpp token probability", "mean": round(statistics.fmean(probs), 4), "token_count": len(probs)})
        if confidence["mean"] < 0.6:
            warnings.append("low mean Whisper token probability")
    elif source.startswith("caption"):
        confidence["method"] = "not exposed by caption source"
    return {
        "status": "FAIL" if errors else ("REVIEW" if warnings else "PASS"),
        "checks": {"segment_count": len(segs), "coverage": round(coverage, 4) if coverage is not None else None, "confidence": confidence},
        "errors": errors,
        "warnings": warnings,
        "validation_scope": "Automated structural/confidence checks; not human ground-truth WER.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Local-first YouTube transcriber for Termux")
    ap.add_argument("url")
    ap.add_argument("--output-root", default=str(Path(__file__).resolve().parent / "output"))
    ap.add_argument("--whisper-cli")
    ap.add_argument("--model")
    ap.add_argument("--force-whisper", action="store_true")
    ap.add_argument("--keep-audio", action="store_true")
    args = ap.parse_args()

    ytdlp, ffmpeg = require("yt-dlp"), require("ffmpeg")
    video_id = extract_video_id(args.url)
    try:
        meta = metadata(args.url, ytdlp)
        video_id = str(meta.get("id") or video_id)
    except Exception as exc:
        print(f"metadata unavailable: {exc}", file=sys.stderr)
        meta = {"id": video_id, "webpage_url": args.url}
    outdir = Path(args.output_root).expanduser().resolve() / video_id
    outdir.mkdir(parents=True, exist_ok=True)
    duration = float(meta.get("duration") or 0.0)
    source_lang = str(meta.get("language") or "") or None
    source = ""
    segs: list[dict[str, Any]] = []
    probs: list[float] = []
    audio: Path | None = None

    if not args.force_whisper:
        selected = select_caption(meta)
        if selected:
            try:
                kind, lang = selected
                segs = download_ytdlp_caption(args.url, ytdlp, outdir, kind, lang)
                source, source_lang = f"caption_{kind}", lang
            except Exception as exc:
                print(f"yt-dlp captions failed: {exc}", file=sys.stderr)
        if not segs:
            preferred = [x for x in (source_lang, "en", "es") if x]
            try:
                segs, kind, source_lang = caption_api(video_id, preferred)
                source = f"caption_api_{kind}"
            except Exception as exc:
                print(f"direct caption API failed: {exc}", file=sys.stderr)
        if not segs:
            preferred = [x for x in (source_lang, "en", "es") if x]
            try:
                segs, kind, source_lang = piped_caption(video_id, preferred)
                source = f"caption_api_{kind}"
            except Exception as exc:
                print(f"Piped fallback failed: {exc}", file=sys.stderr)

    if segs:
        write_outputs(segs, outdir)
    else:
        cli, model = whisper_paths(args.whisper_cli, args.model)
        audio = normalize_audio(args.url, ytdlp, ffmpeg, outdir)
        base = outdir / ".whisper_original"
        text, raw = whisper(cli, model, audio, base)
        segs, probs, detected = whisper_segments(raw, text, duration)
        source_lang = detected or source_lang
        source = "whisper.cpp"
        write_outputs(segs, outdir)
        for suffix in (".txt", ".srt", ".vtt", ".json"):
            Path(str(base) + suffix).unlink(missing_ok=True)

    if is_english(source_lang):
        shutil.copyfile(outdir / "transcript_original.txt", outdir / "transcript_english.txt")
    else:
        cli, model = whisper_paths(args.whisper_cli, args.model)
        if audio is None:
            audio = normalize_audio(args.url, ytdlp, ffmpeg, outdir)
        tbase = outdir / ".whisper_english"
        text, _ = whisper(cli, model, audio, tbase, translate=True)
        (outdir / "transcript_english.txt").write_text(text.strip() + "\n", encoding="utf-8")
        Path(str(tbase) + ".txt").unlink(missing_ok=True)

    report = validate(segs, duration or None, probs, source)
    report.update({"video_id": video_id, "source": source, "source_language": source_lang, "generated_at": now_iso()})
    transcript_json = {"schema_version": SCHEMA_VERSION, "video_id": video_id, "source": source, "source_language": source_lang, "segments": segs, "confidence": report["checks"]["confidence"]}
    metadata_json = {
        "schema_version": SCHEMA_VERSION,
        "video_id": video_id,
        "url": args.url,
        "title": meta.get("title"),
        "channel": meta.get("channel") or meta.get("uploader"),
        "duration_seconds": duration or None,
        "source_language": source_lang,
        "transcript_source": source,
        "transcription_date": now_iso(),
        "output_files": ["transcript_original.txt", "transcript_english.txt", "transcript.srt", "transcript.vtt", "transcript.json", "metadata.json", "validation_report.json"],
    }
    (outdir / "transcript.json").write_text(json.dumps(transcript_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (outdir / "metadata.json").write_text(json.dumps(metadata_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (outdir / "validation_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if not args.keep_audio:
        for p in outdir.glob("source_audio.*"):
            p.unlink(missing_ok=True)
        (outdir / "normalized.wav").unlink(missing_ok=True)
    print(f"{report['status']}: {outdir}")
    return 0 if report["status"] != "FAIL" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"ERROR command failed ({exc.returncode}): {' '.join(exc.cmd)}", file=sys.stderr)
        raise SystemExit(exc.returncode or 1)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
