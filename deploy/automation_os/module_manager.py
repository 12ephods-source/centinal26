#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, shutil, subprocess, tempfile, urllib.request, time

ROOT = pathlib.Path(os.environ.get("AUTOMATION_OS_ROOT", pathlib.Path.home() / "AutomationOS")).expanduser()
REGISTRY = ROOT / "registry" / "registry.json"
STATE = ROOT / "state" / "module_state.json"
CACHE = ROOT / "cache"
MODULES = ROOT / "modules"

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def atomic_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)

def state():
    if STATE.exists():
        return load_json(STATE)
    return {"schema_version": 1, "modules": {}, "history": []}

def save_state(s):
    atomic_json(STATE, s)

def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def raw_url(src):
    return f"https://raw.githubusercontent.com/{src['repository']}/{src['commit']}/{src['path']}"

def download_module(name, spec, dry_run=False):
    src = spec["source"]
    CACHE.mkdir(parents=True, exist_ok=True)
    if src["kind"] == "github_raw_git_blob":
        url = raw_url(src)
        dest = CACHE / pathlib.Path(src["path"]).name
        if dry_run:
            return {"module": name, "url": url, "dest": str(dest), "dry_run": True}
        with urllib.request.urlopen(url, timeout=60) as r:
            data = r.read()
        actual = git_blob_sha1(data)
        expected = src["git_blob_sha1"]
        if actual != expected:
            raise RuntimeError(f"{name}: Git blob mismatch expected={expected} actual={actual}")
        dest.write_bytes(data)
        os.chmod(dest, 0o700)
        return {"module": name, "url": url, "dest": str(dest), "git_blob_sha1": actual}
    if src["kind"] == "bundled_file":
        p = ROOT / src["path"]
        if not p.exists():
            raise FileNotFoundError(p)
        return {"module": name, "dest": str(p), "bundled": True}
    raise ValueError(f"unsupported source kind {src['kind']}")

def validate_shell(path):
    proc = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or "bash -n failed")
    return True

def require_termux():
    prefix = os.environ.get("PREFIX", "")
    if "com.termux" not in prefix and os.environ.get("AUTOMATION_OS_TEST_MODE") != "1":
        raise RuntimeError("This module requires Termux on Android.")

def install_module(name, reg, execute=True, dry_run=False):
    if name not in reg["modules"]:
        raise KeyError(name)
    spec = reg["modules"][name]
    if spec["install"].get("requires_termux"):
        require_termux()
    got = download_module(name, spec, dry_run=dry_run)
    if dry_run:
        return got
    path = pathlib.Path(got["dest"])
    if spec["install"]["type"] == "shell":
        validate_shell(path)
        if execute:
            result = subprocess.run(["bash", str(path)])
            if result.returncode:
                raise RuntimeError(f"{name}: installer exited {result.returncode}")
    s = state()
    s["modules"][name] = {
        "status": "INSTALLED" if execute else "STAGED",
        "installed_at": int(time.time()),
        "source": spec["source"],
        "artifact": str(path)
    }
    s["history"].append({"event": "module_install", "module": name, "execute": execute, "ts": int(time.time())})
    save_state(s)
    return s["modules"][name]

def install_profile(profile, execute=True, dry_run=False):
    reg = load_json(REGISTRY)
    names = reg["profiles"].get(profile)
    if names is None:
        raise KeyError(f"unknown profile {profile}")
    result = {}
    for name in names:
        result[name] = install_module(name, reg, execute=execute, dry_run=dry_run)
    return result

def verify_state():
    reg = load_json(REGISTRY)
    s = state()
    report = {"ok": True, "modules": {}}
    for name, rec in s["modules"].items():
        spec = reg["modules"].get(name)
        item = {"status": rec.get("status")}
        p = pathlib.Path(rec.get("artifact", ""))
        item["artifact_exists"] = p.exists()
        if p.exists() and spec and spec["source"]["kind"] == "github_raw_git_blob":
            actual = git_blob_sha1(p.read_bytes())
            item["git_blob_sha1"] = actual
            item["expected"] = spec["source"]["git_blob_sha1"]
            item["identity_ok"] = actual == item["expected"]
        else:
            item["identity_ok"] = p.exists()
        report["ok"] = report["ok"] and item["artifact_exists"] and item["identity_ok"]
        report["modules"][name] = item
    return report

def self_test():
    sample = b"hello automation os\n"
    expected = hashlib.sha1(b"blob " + str(len(sample)).encode() + b"\0" + sample).hexdigest()
    assert git_blob_sha1(sample) == expected
    reg = load_json(REGISTRY)
    assert "frost-fleet-v1.7" in reg["modules"]
    assert reg["integrity_policy"]["fail_closed"] is True
    assert "Guardian" in reg["unregistered_components"]
    return {"status": "PASS", "tests": 4}

def main():
    ap = argparse.ArgumentParser(prog="frost-install")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    p = sub.add_parser("plan"); p.add_argument("profile")
    p = sub.add_parser("install"); p.add_argument("profile"); p.add_argument("--stage-only", action="store_true")
    sub.add_parser("status")
    sub.add_parser("verify")
    sub.add_parser("self-test")
    args = ap.parse_args()
    reg = load_json(REGISTRY)
    if args.cmd == "list":
        print(json.dumps({"profiles": reg["profiles"], "modules": reg["modules"], "unregistered": reg["unregistered_components"]}, indent=2))
    elif args.cmd == "plan":
        print(json.dumps(install_profile(args.profile, execute=False, dry_run=True), indent=2))
    elif args.cmd == "install":
        print(json.dumps(install_profile(args.profile, execute=not args.stage_only), indent=2))
    elif args.cmd == "status":
        print(json.dumps(state(), indent=2))
    elif args.cmd == "verify":
        r = verify_state(); print(json.dumps(r, indent=2)); raise SystemExit(0 if r["ok"] else 2)
    elif args.cmd == "self-test":
        print(json.dumps(self_test(), indent=2))

if __name__ == "__main__":
    main()
