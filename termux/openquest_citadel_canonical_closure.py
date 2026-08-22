#!/usr/bin/env python3
"""Bounded exact-source canonical validation for The Devouring Citadel.

This utility never installs over the user's normal OpenQuest tree. It locates the
historical OpenQuest 6.0.0-rc.1 installer, verifies its embedded payload by exact
size and SHA-256, extracts it into an isolated temporary directory, verifies
pinned canonical source identities, runs the Tier-5 authoring regression, then
submits the repository-pinned Citadel module to the canonical localhost APIs.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath

CANDIDATE_OQMOD_SHA256 = "9f2859183353d912b50638669a37e3d39f1110ecf7de3565b4632759015c5da0"
CANDIDATE_SEMANTIC_SHA256 = "a536a6b72c772775d7d8d5214371643a7d6e212264c85ba0dc3b07315fd0e074"
RC1_PAYLOAD_BYTES = 3_458_656
RC1_PAYLOAD_SHA256 = "3e5a424e57b13f383d89daf1cf1337cdcb287771406a1c1242f33fe495c65c25"
PINNED_FILES = {
    "config/module-schema-v6.json": (10_436, "8d9aa1b17aae8511b07c00b1f48f29bf1314ad63836608c78f96b7e76cc38de2"),
    "authoring.py": (34_009, "3e46ab115914272c7d092996b24332fad41d670c6a87e0e1b1535bbea4df5b1a"),
    "server.py": (70_621, "804c74bdc790665945e6d25fa0c2519b816b941ca137ff1cd487d795c3c1f81d"),
    "module-template.example.json": (4_298, "0f4f6a3e604e98dfe9814c2f328b91cf6679cc901214ecb5ed224f422b2ec435"),
    "tests/test_tier5_authoring.py": (2_692, "ef14bfa5c19c3b3c5aeca4a66c8bf24129e41aaf6b0df75248d6f960a883f16e"),
}
DEFAULT_MODULE = Path(__file__).resolve().parents[1] / "projects" / "openquest" / "the_devouring_citadel" / "module.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def candidate_dirs() -> list[Path]:
    home = Path.home()
    values = [
        Path.cwd(),
        home / "storage" / "shared" / "Download",
        home / "storage" / "downloads",
        home / "Downloads",
        home / "downloads",
        Path("/sdcard/Download"),
        Path("/storage/emulated/0/Download"),
    ]
    return [path for path in values if path.is_dir()]


def decode_rc1_payload(path: Path) -> bytes | None:
    try:
        if path.stat().st_size > 24 * 1024 * 1024:
            return None
        text = path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeError):
        return None
    start = "__OPENQUEST_PAYLOAD_BEGIN__\n"
    end = "\n__OPENQUEST_PAYLOAD_END__"
    if start not in text or end not in text:
        return None
    try:
        raw = base64.b64decode("".join(text.split(start, 1)[1].split(end, 1)[0].split()), validate=True)
    except (ValueError, base64.binascii.Error):
        return None
    if len(raw) != RC1_PAYLOAD_BYTES or sha256_bytes(raw) != RC1_PAYLOAD_SHA256:
        return None
    return raw


def find_rc1(explicit: Path | None = None) -> tuple[Path, bytes]:
    if explicit is not None:
        raw = decode_rc1_payload(explicit)
        if raw is None:
            raise RuntimeError("explicit installer does not match the frozen RC1 payload authority")
        return explicit, raw

    exact_names = (
        "OpenQuestRPG-6.0.0-RC1-TERMUX_ONE_PASTE.sh",
        "OpenQuestRPG-6.0.0-RC1-TERMUX_ONE_PASTE.txt",
    )
    for directory in candidate_dirs():
        for name in exact_names:
            path = directory / name
            if path.is_file():
                raw = decode_rc1_payload(path)
                if raw is not None:
                    return path, raw

    seen: set[Path] = set()
    for directory in candidate_dirs()[1:]:
        for root_text, dirs, files in os.walk(directory):
            root = Path(root_text)
            try:
                depth = len(root.relative_to(directory).parts)
            except ValueError:
                continue
            if depth >= 5:
                dirs.clear()
            for name in files:
                path = root / name
                if path in seen:
                    continue
                seen.add(path)
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                if size > 24 * 1024 * 1024:
                    continue
                if path.suffix.lower() not in {".sh", ".txt"} and "openquest" not in path.name.lower() and "rc1" not in path.name.lower():
                    continue
                raw = decode_rc1_payload(path)
                if raw is not None:
                    return path, raw
    raise FileNotFoundError("exact OpenQuest 6.0.0-rc.1 installer payload not found in approved download paths")


def safe_extract_tar(raw: bytes, dest: Path) -> Path:
    archive = dest / "source.tar.gz"
    archive.write_bytes(raw)
    root = dest / "extracted"
    root.mkdir()
    with tarfile.open(archive, "r:gz") as tf:
        members = tf.getmembers()
        if not 1 <= len(members) <= 10_000:
            raise RuntimeError("implausible RC1 archive member count")
        total = 0
        for member in members:
            name = PurePosixPath(member.name.replace("\\", "/"))
            if name.is_absolute() or ".." in name.parts:
                raise RuntimeError(f"unsafe RC1 archive path: {member.name}")
            if member.issym() or member.islnk() or member.isdev():
                raise RuntimeError(f"unsafe RC1 archive member type: {member.name}")
            total += max(0, member.size)
            if total > 512 * 1024 * 1024:
                raise RuntimeError("expanded RC1 source exceeds safety ceiling")
        try:
            tf.extractall(root, filter="data")
        except TypeError:
            tf.extractall(root)
    source = root / "openquest-rpg"
    if not source.is_dir():
        raise RuntimeError("canonical source root missing after extraction")
    return source


def verify_pins(source: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for rel, (expected_bytes, expected_sha) in PINNED_FILES.items():
        path = source / rel
        if not path.is_file():
            raise RuntimeError(f"pinned canonical source missing: {rel}")
        actual_bytes = path.stat().st_size
        actual_sha = sha256_file(path)
        ok = actual_bytes == expected_bytes and actual_sha == expected_sha
        rows.append({"path": rel, "bytes": actual_bytes, "sha256": actual_sha, "pass": ok})
        if not ok:
            raise RuntimeError(f"pinned canonical identity mismatch: {rel}")
    return rows


def http_json(url: str, method: str = "GET", obj: object | None = None) -> dict[str, object]:
    data = None if obj is None else json.dumps(obj, ensure_ascii=False).encode()
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            body = response.read()
            try:
                parsed = json.loads(body) if body else None
            except json.JSONDecodeError:
                parsed = None
            return {"status": response.status, "json": parsed, "body": body.decode("utf-8", errors="replace")[-20_000:]}
    except urllib.error.HTTPError as exc:
        body = exc.read()
        try:
            parsed = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed = None
        return {"status": exc.code, "json": parsed, "body": body.decode("utf-8", errors="replace")[-20_000:]}
    except OSError as exc:
        return {"status": 0, "error": repr(exc)}


def semantic_pass(response: dict[str, object]) -> bool:
    if response.get("status") not in {200, 201}:
        return False
    payload = response.get("json")
    if isinstance(payload, bool):
        return payload
    if not isinstance(payload, dict):
        return False
    if payload.get("valid") is False or payload.get("ok") is False or payload.get("error") or payload.get("errors"):
        return False
    if payload.get("valid") is True or payload.get("ok") is True:
        return True
    issues = payload.get("issues")
    if issues is None:
        issues = payload.get("lint")
    if issues is None:
        issues = payload.get("messages")
    if isinstance(issues, list):
        return not any(
            isinstance(item, dict) and str(item.get("severity", "")).lower() in {"error", "fatal"}
            for item in issues
        )
    return False


def module_variants(module: dict[str, object]) -> list[tuple[str, dict[str, object]]]:
    variants = [("baseline_worldVariables", module)]
    if "worldVariables" in module and "world" not in module:
        alternate = json.loads(json.dumps(module))
        alternate["world"] = {"variables": alternate.pop("worldVariables")}
        variants.append(("documented_world_dot_variables", alternate))
    return variants


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rc1", type=Path)
    parser.add_argument("--module", type=Path, default=DEFAULT_MODULE)
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args()

    module_path = args.module.expanduser().resolve()
    module = json.loads(module_path.read_text(encoding="utf-8"))
    if module.get("schemaVersion") != 6 or module.get("version") != "1.3.0":
        raise SystemExit("unexpected Citadel module identity")

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    evidence_dir = (args.evidence_dir or (Path.home() / ".local" / "state" / "openquest-citadel" / stamp)).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    semantic_blob = json.dumps(module, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    semantic_sha = sha256_bytes(semantic_blob)
    if semantic_sha != CANDIDATE_SEMANTIC_SHA256:
        raise SystemExit("repository module content does not match the frozen v1.3 candidate semantics")
    report: dict[str, object] = {
        "schema": 1,
        "started_utc": stamp,
        "candidate": {
            "path": str(module_path),
            "source_sha256": sha256_file(module_path),
            "semantic_sha256": semantic_sha,
            "oqmod_sha256": CANDIDATE_OQMOD_SHA256,
        },
        "gates": {},
    }

    installer, raw = find_rc1(args.rc1.expanduser().resolve() if args.rc1 else None)
    report["rc1"] = {"path": str(installer), "payload_bytes": len(raw), "payload_sha256": sha256_bytes(raw)}

    with tempfile.TemporaryDirectory(prefix="openquest-citadel-") as td:
        source = safe_extract_tar(raw, Path(td))
        pins = verify_pins(source)
        report["gates"]["source_identity"] = {"pass": True, "files": pins}  # type: ignore[index]

        tier5 = source / "tests" / "test_tier5_authoring.py"
        cp = subprocess.run([sys.executable, str(tier5)], cwd=source, text=True, capture_output=True, timeout=120, check=False)
        (evidence_dir / "tier5.stdout.txt").write_text(cp.stdout, encoding="utf-8")
        (evidence_dir / "tier5.stderr.txt").write_text(cp.stderr, encoding="utf-8")
        report["gates"]["tier5_regression"] = {"pass": cp.returncode == 0, "returncode": cp.returncode}  # type: ignore[index]
        if cp.returncode != 0:
            report["result"] = "FAIL_CANONICAL_TIER5_REGRESSION"
            (evidence_dir / "CANONICAL_CLOSURE_EVIDENCE.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
            return 42

        port = free_port()
        env = os.environ.copy()
        env.update({
            "OPENQUEST_HOST": "127.0.0.1",
            "OPENQUEST_PORT": str(port),
            "OPENQUEST_TEST_MODE": "1",
            "OPENQUEST_NO_OPEN": "1",
            "OPENQUEST_DATA_DIR": str(evidence_dir / "isolated-data"),
            "OPENQUEST_SAVE_DIR": str(evidence_dir / "isolated-data" / "saves"),
            "OPENQUEST_USER_MODULE_DIR": str(evidence_dir / "isolated-data" / "modules"),
            "OPENQUEST_MODULE_ASSET_DIR": str(evidence_dir / "isolated-data" / "module-assets"),
        })
        server = source / "server.py"
        help_cp = subprocess.run([sys.executable, str(server), "--help"], cwd=source, env=env, text=True, capture_output=True, timeout=10, check=False)
        help_text = help_cp.stdout + help_cp.stderr
        command = [sys.executable, str(server), "--host", "127.0.0.1", "--port", str(port)] if "--port" in help_text else [sys.executable, str(server)]
        with (evidence_dir / "server.log").open("wb") as log:
            proc = subprocess.Popen(command, cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                base = f"http://127.0.0.1:{port}"
                ready = None
                for _ in range(120):
                    if proc.poll() is not None:
                        break
                    status = http_json(base + "/api/status")
                    if status.get("status") == 200:
                        ready = status
                        break
                    time.sleep(0.1)
                report["gates"]["server_ready"] = {"pass": ready is not None, "response": ready}  # type: ignore[index]
                if ready is None:
                    report["result"] = "FAIL_CANONICAL_SERVER_NOT_READY"
                    return_code = 43
                else:
                    variant_results: list[dict[str, object]] = []
                    passing: list[tuple[str, dict[str, object]]] = []
                    for name, variant in module_variants(module):
                        attempts = []
                        for form, obj in (("wrapped_module", {"module": variant}), ("raw_module", variant), ("wrapped_document", {"document": variant})):
                            response = http_json(base + "/api/authoring/validate", "POST", obj)
                            ok = semantic_pass(response)
                            attempts.append({"form": form, "pass": ok, "response": response})
                            if ok:
                                break
                        ok = any(item["pass"] for item in attempts)
                        variant_results.append({"variant": name, "pass": ok, "attempts": attempts})
                        if ok:
                            passing.append((name, variant))
                    report["gates"]["schema_validation"] = {"pass": bool(passing), "variants": variant_results}  # type: ignore[index]
                    if not passing:
                        report["result"] = "FAIL_SCHEMA_VALIDATION_NO_SUPPORTED_VARIANT"
                        return_code = 44
                    else:
                        selected = next((item for item in passing if item[0] == "baseline_worldVariables"), passing[0])
                        selected_name, selected_module = selected
                        report["selected_variant"] = selected_name
                        (evidence_dir / "SELECTED_CANONICAL_MODULE.json").write_text(json.dumps(selected_module, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                        acceptance = http_json(base + "/api/modules", "POST", selected_module)
                        accepted = acceptance.get("status") in {200, 201} and not (
                            isinstance(acceptance.get("json"), dict)
                            and (acceptance["json"].get("error") or acceptance["json"].get("errors"))
                        )
                        report["gates"]["module_acceptance"] = {"pass": accepted, "response": acceptance}  # type: ignore[index]
                        package_attempts = []
                        for form, obj in (("wrapped_module", {"module": selected_module}), ("raw_module", selected_module)):
                            response = http_json(base + "/api/authoring/package", "POST", obj)
                            package_attempts.append({"form": form, "response": response})
                            if response.get("status") == 201:
                                break
                        package_ok = any(item["response"].get("status") == 201 for item in package_attempts)
                        report["gates"]["package_api"] = {"pass": package_ok, "attempts": package_attempts}  # type: ignore[index]
                        if accepted:
                            report["result"] = "PASS_SCHEMA_AND_MODULE" if not package_ok else "PASS_SCHEMA_MODULE_AND_PACKAGE"
                            return_code = 0
                        else:
                            report["result"] = "FAIL_CANONICAL_MODULE_ACCEPTANCE"
                            return_code = 45
            finally:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except (OSError, subprocess.SubprocessError):
                    proc.kill()

    report["ended_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    evidence_file = evidence_dir / "CANONICAL_CLOSURE_EVIDENCE.json"
    evidence_file.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"result": report.get("result"), "evidence": str(evidence_file)}, indent=2))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
