from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import time
import urllib.request

ROOT = pathlib.Path(
    os.environ.get("AUTOMATION_OS_ROOT", pathlib.Path.home() / "AutomationOS")
).expanduser()
REGISTRY = ROOT / "registry" / "registry.json"
STATE = ROOT / "state" / "module_state.json"
CACHE = ROOT / "cache"


def load_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: pathlib.Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def state() -> dict:
    if STATE.exists():
        return load_json(STATE)
    return {"schema_version": 1, "modules": {}, "history": []}


def save_state(value: dict) -> None:
    atomic_json(STATE, value)


def append_history(value: dict, **event) -> None:
    event.setdefault("ts", int(time.time()))
    value["history"].append(event)


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode() + b"\0" + data,
        usedforsecurity=False,
    ).hexdigest()


def raw_url(source: dict) -> str:
    return (
        f"https://raw.githubusercontent.com/{source['repository']}/"
        f"{source['commit']}/{source['path']}"
    )


def download_module(name: str, spec: dict, dry_run: bool = False) -> dict:
    source = spec["source"]
    if source["kind"] != "github_raw_git_blob":
        raise ValueError(f"{name}: unsupported source kind {source['kind']}")
    CACHE.mkdir(parents=True, exist_ok=True)
    url = raw_url(source)
    dest = CACHE / f"{name}--{pathlib.Path(source['path']).name}"
    if dry_run:
        return {"module": name, "url": url, "dest": str(dest), "dry_run": True}

    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read()

    actual = git_blob_sha1(data)
    expected = source["git_blob_sha1"]
    if actual != expected:
        raise RuntimeError(
            f"{name}: Git blob mismatch expected={expected} actual={actual}"
        )
    dest.write_bytes(data)
    os.chmod(dest, 0o700)
    return {
        "module": name,
        "url": url,
        "dest": str(dest),
        "git_blob_sha1": actual,
    }


def validate_shell(path: pathlib.Path) -> None:
    result = subprocess.run(
        ["bash", "-n", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "bash -n failed")


def require_termux() -> None:
    prefix = os.environ.get("PREFIX", "")
    if (
        "com.termux" not in prefix
        and os.environ.get("AUTOMATION_OS_TEST_MODE") != "1"
    ):
        raise RuntimeError("This module requires Termux on Android.")


def installed_identity_ok(name: str, spec: dict, value: dict) -> bool:
    record = value["modules"].get(name)
    if not record or record.get("status") != "INSTALLED":
        return False
    artifact = pathlib.Path(record.get("artifact", ""))
    if not artifact.exists():
        return False
    source = spec["source"]
    return git_blob_sha1(artifact.read_bytes()) == source["git_blob_sha1"]


def install_module(
    name: str,
    registry: dict,
    *,
    execute: bool = True,
    dry_run: bool = False,
    stack: tuple[str, ...] = (),
) -> dict:
    if name in stack:
        raise RuntimeError("dependency cycle: " + " -> ".join((*stack, name)))
    if name not in registry["modules"]:
        raise KeyError(f"unknown module {name}")

    spec = registry["modules"][name]
    plan: dict[str, object] = {"module": name, "dependencies": []}
    for dependency in spec.get("depends_on", []):
        dep_result = install_module(
            dependency,
            registry,
            execute=execute,
            dry_run=dry_run,
            stack=(*stack, name),
        )
        plan["dependencies"].append(dep_result)

    if spec["install"].get("requires_termux"):
        require_termux()

    if dry_run:
        plan["artifact"] = download_module(name, spec, dry_run=True)
        plan["execute"] = execute
        return plan

    value = state()
    if execute and installed_identity_ok(name, spec, value):
        append_history(value, event="module_skip_verified", module=name)
        save_state(value)
        return {"module": name, "status": "ALREADY_INSTALLED_VERIFIED"}

    got = download_module(name, spec)
    path = pathlib.Path(got["dest"])
    if spec["install"]["type"] != "shell":
        raise ValueError(f"{name}: unsupported install type")
    validate_shell(path)

    try:
        if execute:
            result = subprocess.run(["bash", str(path)], check=False)
            if result.returncode:
                raise RuntimeError(f"{name}: installer exited {result.returncode}")
    except Exception as exc:
        value = state()
        value["modules"][name] = {
            "status": "FAILED",
            "failed_at": int(time.time()),
            "source": spec["source"],
            "artifact": str(path),
            "reason": str(exc),
        }
        append_history(
            value,
            event="module_install_failed",
            module=name,
            reason=str(exc),
        )
        save_state(value)
        raise

    value = state()
    value["modules"][name] = {
        "status": "INSTALLED" if execute else "STAGED",
        "installed_at": int(time.time()),
        "source": spec["source"],
        "artifact": str(path),
    }
    append_history(
        value,
        event="module_install",
        module=name,
        execute=execute,
    )
    save_state(value)
    return value["modules"][name]


def install_profile(
    profile: str,
    *,
    execute: bool = True,
    dry_run: bool = False,
) -> dict:
    registry = load_json(REGISTRY)
    names = registry["profiles"].get(profile)
    if names is None:
        raise KeyError(f"unknown profile {profile}")
    return {
        name: install_module(
            name,
            registry,
            execute=execute,
            dry_run=dry_run,
        )
        for name in names
    }


def verify_state() -> dict:
    registry = load_json(REGISTRY)
    value = state()
    report = {"ok": True, "modules": {}}
    for name, record in value["modules"].items():
        spec = registry["modules"].get(name)
        item = {"status": record.get("status"), "registered": spec is not None}
        artifact = pathlib.Path(record.get("artifact", ""))
        item["artifact_exists"] = artifact.exists()
        if (
            artifact.exists()
            and spec
            and spec["source"]["kind"] == "github_raw_git_blob"
        ):
            actual = git_blob_sha1(artifact.read_bytes())
            item["git_blob_sha1"] = actual
            item["expected"] = spec["source"]["git_blob_sha1"]
            item["identity_ok"] = actual == item["expected"]
        else:
            item["identity_ok"] = False
        item_ok = (
            item["registered"]
            and item["artifact_exists"]
            and item["identity_ok"]
            and record.get("status") in {"INSTALLED", "STAGED"}
        )
        report["ok"] = report["ok"] and item_ok
        report["modules"][name] = item
    return report


def self_test() -> dict:
    sample = b"hello automation os\n"
    expected = hashlib.sha1(
        b"blob " + str(len(sample)).encode() + b"\0" + sample,
        usedforsecurity=False,
    ).hexdigest()
    assert git_blob_sha1(sample) == expected
    registry = load_json(REGISTRY)
    assert registry["integrity_policy"]["fail_closed"] is True
    assert "frost-fleet-v1.7" in registry["modules"]
    assert "hermes-c05-v1.0" in registry["modules"]
    assert "centinal26-core-v1.0" in registry["modules"]
    assert registry["modules"]["capability-provider-v1.0"]["depends_on"] == [
        "base44-worker-v1.0"
    ]
    assert "AICCEP-OS" in registry["known_artifacts_not_remotely_installable"]
    return {"status": "PASS", "tests": 6}


def main() -> None:
    parser = argparse.ArgumentParser(prog="frost-install")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    plan = sub.add_parser("plan")
    plan.add_argument("profile")
    install = sub.add_parser("install")
    install.add_argument("profile")
    install.add_argument("--stage-only", action="store_true")
    sub.add_parser("status")
    sub.add_parser("verify")
    sub.add_parser("self-test")
    args = parser.parse_args()

    registry = load_json(REGISTRY)
    if args.cmd == "list":
        print(
            json.dumps(
                {
                    "profiles": registry["profiles"],
                    "profile_notes": registry.get("profile_notes", {}),
                    "modules": registry["modules"],
                    "known_not_installable": registry[
                        "known_artifacts_not_remotely_installable"
                    ],
                },
                indent=2,
            )
        )
    elif args.cmd == "plan":
        print(json.dumps(install_profile(args.profile, execute=False, dry_run=True), indent=2))
    elif args.cmd == "install":
        print(
            json.dumps(
                install_profile(
                    args.profile,
                    execute=not args.stage_only,
                ),
                indent=2,
            )
        )
    elif args.cmd == "status":
        print(json.dumps(state(), indent=2))
    elif args.cmd == "verify":
        report = verify_state()
        print(json.dumps(report, indent=2))
        raise SystemExit(0 if report["ok"] else 2)
    elif args.cmd == "self-test":
        print(json.dumps(self_test(), indent=2))


if __name__ == "__main__":
    main()
