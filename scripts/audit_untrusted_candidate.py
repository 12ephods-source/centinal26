from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

MAX_TEXT_BYTES = 2_000_000
TEXT_SUFFIXES = {
    ".sh", ".bash", ".zsh", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf", ".md", ".txt", ".env",
}

# This is a risk classifier, not a malware oracle. Critical findings are denied by default.
RULES: tuple[tuple[str, str, str], ...] = (
    ("REMOTE_PIPE_EXEC", "critical", r"(?:curl|wget)[^\n|]{0,500}\|\s*(?:ba)?sh\b"),
    ("SHELL_EVAL_REMOTE", "critical", r"(?:eval|source|\.)\s+[^\n]{0,200}(?:curl|wget)"),
    ("DESTRUCTIVE_ROOT_DELETE", "critical", r"\brm\s+-[^\n]{0,20}r[^\n]{0,20}f[^\n]{0,80}(?:/|\$HOME|~)\b"),
    ("RAW_BLOCK_DEVICE", "critical", r"\b(?:dd\s+if=|mkfs(?:\.|\s)|wipefs\b|fdisk\b)"),
    ("PRIVILEGE_ESCALATION", "critical", r"\b(?:su|sudo|tsu)\b"),
    ("SHELL_TRUE", "critical", r"(?:subprocess\.[A-Za-z_]+|Popen)\([^\n]{0,500}shell\s*=\s*True"),
    ("PYTHON_DYNAMIC_EXEC", "high", r"\b(?:eval|exec)\s*\("),
    ("OS_SYSTEM", "high", r"\bos\.system\s*\("),
    ("BOOT_PERSISTENCE", "high", r"(?:\.termux/boot|crontab\b|systemd\b|nohup\b)"),
    ("CREDENTIAL_PATH", "high", r"(?:\.ssh/|\.aws/|\.gnupg/|\.config/gh/|\.env\b|keyring|keystore)"),
    ("TOKEN_REFERENCE", "high", r"\b(?:GITHUB_TOKEN|GH_TOKEN|OPENAI_API_KEY|ANTHROPIC_API_KEY|GOOGLE_API_KEY|API_KEY|PASSWORD|PASSWD|PIN)\b"),
    ("DEVICE_SETTINGS", "high", r"\b(?:settings\s+put|pm\s+(?:install|uninstall|disable)|am\s+(?:start|broadcast)|adb\s+)"),
    ("NETWORK_TOOL", "medium", r"\b(?:curl|wget|nc|ncat|ssh|scp|sftp|rsync|tor)\b"),
    ("PACKAGE_INSTALL", "medium", r"\b(?:pip|pip3|npm|pnpm|yarn|apt|pkg)\s+install\b"),
    ("SUBPROCESS", "medium", r"\bsubprocess\.(?:run|Popen|call|check_call|check_output)\b"),
    ("OBFUSCATED_DECODE", "high", r"(?:base64\s+(?:-d|--decode)|b64decode\s*\(|fromhex\s*\()"),
    ("REBOOT", "high", r"\b(?:reboot|termux-reboot)\b"),
)


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    path: str
    line: int
    excerpt: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_member(info: zipfile.ZipInfo) -> tuple[bool, str | None]:
    raw = info.filename.replace("\\", "/")
    path = PurePosixPath(raw)
    if not raw or raw.startswith("/") or path.is_absolute() or ".." in path.parts:
        return False, "PATH_TRAVERSAL"
    mode = info.external_attr >> 16
    if mode and stat.S_ISLNK(mode):
        return False, "SYMLINK_MEMBER"
    return True, None


def looks_text(path: str, data: bytes) -> bool:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return True
    if b"\x00" in data[:4096]:
        return False
    try:
        data[:4096].decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def scan_text(path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        for rule, severity, pattern in RULES:
            if re.search(pattern, line, flags=re.IGNORECASE):
                excerpt = line.strip()
                if len(excerpt) > 240:
                    excerpt = excerpt[:237] + "..."
                findings.append(Finding(rule, severity, path, line_number, excerpt))
    return findings


def audit_zip(path: Path, expected_sha256: str | None = None) -> dict[str, object]:
    report: dict[str, object] = {
        "schema": "centinal26-untrusted-candidate-audit-v1",
        "artifact": str(path),
        "sha256": None,
        "expected_sha256": expected_sha256,
        "hash_match": None,
        "archive_safe": False,
        "members": 0,
        "text_members_scanned": 0,
        "findings": [],
        "decision": "DENY",
        "reason": None,
        "note": "A matching pin authenticates bytes only; it does not establish benign behavior.",
    }
    if not path.is_file():
        report["reason"] = "ARTIFACT_NOT_FOUND"
        return report

    actual = sha256(path)
    report["sha256"] = actual
    if expected_sha256 is not None:
        report["hash_match"] = actual == expected_sha256.lower()
        if not report["hash_match"]:
            report["reason"] = "HASH_MISMATCH"
            return report

    findings: list[Finding] = []
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            report["members"] = len(infos)
            for info in infos:
                safe, reason = safe_member(info)
                if not safe:
                    findings.append(Finding(reason or "UNSAFE_MEMBER", "critical", info.filename, 0, info.filename))
                    continue
                if info.is_dir():
                    continue
                if info.file_size > MAX_TEXT_BYTES:
                    continue
                data = archive.read(info)
                if not looks_text(info.filename, data):
                    continue
                report["text_members_scanned"] = int(report["text_members_scanned"]) + 1
                text = data.decode("utf-8", errors="replace")
                findings.extend(scan_text(info.filename, text))
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        report["reason"] = f"INVALID_ARCHIVE:{type(exc).__name__}"
        return report

    report["archive_safe"] = not any(
        item.severity == "critical" and item.rule in {"PATH_TRAVERSAL", "SYMLINK_MEMBER"}
        for item in findings
    )
    report["findings"] = [asdict(item) for item in findings]
    blocking = [item for item in findings if item.severity in {"critical", "high"}]
    if not report["archive_safe"]:
        report["reason"] = "UNSAFE_ARCHIVE_STRUCTURE"
    elif blocking:
        report["reason"] = "BEHAVIOR_REVIEW_REQUIRED"
    else:
        report["decision"] = "ALLOW_STATIC_ONLY"
        report["reason"] = "NO_BLOCKING_STATIC_FINDINGS"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed static audit for untrusted ZIP candidates.")
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_zip(args.artifact.expanduser(), args.expected_sha256)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.expanduser().write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)
    return 0 if report["decision"] == "ALLOW_STATIC_ONLY" else 23


if __name__ == "__main__":
    raise SystemExit(main())
