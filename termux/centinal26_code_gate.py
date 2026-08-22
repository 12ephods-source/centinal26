from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("CENTINAL26_HOME", str(Path.home() / ".centinal26"))).expanduser()
INBOX = ROOT / "code_inbox"
EVID = ROOT / "evidence" / "code_gate"
REPORTS = ROOT / "reports" / "code_gate"
for directory in (INBOX, EVID, REPORTS):
    directory.mkdir(parents=True, exist_ok=True)

MAX_PASSES = 5


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def origin() -> str:
    prefix = os.environ.get("PREFIX", "")
    return "ANDROID_TERMUX_DEVICE" if "com.termux" in prefix else "LOCAL_RUNTIME"


def environment_identity() -> dict:
    return {
        "origin_class": origin(),
        "prefix": os.environ.get("PREFIX"),
        "python": sys.version.split()[0],
        "platform": sys.platform,
    }


def run(argv: list[str], cwd: Path, timeout: int = 180) -> dict:
    started = time.time()
    completed = subprocess.run(
        argv,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "argv": argv,
        "returncode": completed.returncode,
        "stdout": completed.stdout[-12000:],
        "stderr": completed.stderr[-12000:],
        "duration_s": round(time.time() - started, 3),
    }


def classify(path: Path) -> str:
    if path.suffix == ".py":
        return "python"
    if path.suffix in {".sh", ".bash"}:
        return "shell"
    if path.suffix == ".js":
        return "javascript"
    if path.suffix == ".ts":
        return "typescript"
    return "unknown"


def safety_scan(path: Path) -> dict:
    text = path.read_text(errors="replace").lower()
    findings: list[str] = []
    if "curl" in text and "|" in text and "sh" in text:
        findings.append("network-pipe-to-shell")
    if "wget" in text and "|" in text and "sh" in text:
        findings.append("download-pipe-to-shell")
    if "rm" in text and "-rf" in text and " /" in text:
        findings.append("root-recursive-delete")
    return {"status": "PASS" if not findings else "REVIEW", "findings": findings}


def tests(path: Path, language: str) -> list[dict]:
    cwd = path.parent
    results: list[dict] = []
    if language == "python":
        results.append(run([sys.executable, "-m", "py_compile", str(path)], cwd))
        if shutil.which("ruff"):
            results.append(run(["ruff", "check", str(path)], cwd))
        if (cwd / "tests").exists() and shutil.which("pytest"):
            results.append(run(["pytest", "-q"], cwd, timeout=900))
    elif language == "shell":
        results.append(run(["bash", "-n", str(path)], cwd))
        if shutil.which("shellcheck"):
            results.append(run(["shellcheck", str(path)], cwd))
    elif language == "javascript" and shutil.which("node"):
        results.append(run(["node", "--check", str(path)], cwd))
    elif language == "typescript" and shutil.which("tsc"):
        results.append(run(["tsc", "--noEmit", str(path)], cwd, timeout=900))
    else:
        results.append(
            {
                "argv": [],
                "returncode": 2,
                "stdout": "",
                "stderr": "unsupported language or missing validator",
                "duration_s": 0,
            }
        )
    return results


def deterministic_improve(path: Path, language: str) -> dict:
    before = sha(path)
    actions: list[dict] = []
    if language == "python" and shutil.which("ruff"):
        actions.append(run(["ruff", "check", "--fix", str(path)], path.parent))
        if shutil.which("black"):
            actions.append(run(["black", "-q", str(path)], path.parent))
    elif language == "shell" and shutil.which("shfmt"):
        actions.append(run(["shfmt", "-w", str(path)], path.parent))
    return {
        "changed": sha(path) != before,
        "actions": actions,
        "before_sha256": before,
        "after_sha256": sha(path),
    }


def execute(path: Path, language: str, args: list[str], timeout: int) -> dict:
    if language == "python":
        argv = [sys.executable, str(path), *args]
    elif language == "shell":
        argv = ["bash", str(path), *args]
    elif language == "javascript":
        argv = ["node", str(path), *args]
    else:
        raise SystemExit("execution unsupported for language")
    return run(argv, path.parent, min(timeout, 900))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--arg", action="append", default=[])
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--no-run", action="store_true")
    args = parser.parse_args()

    source = Path(args.path).expanduser().resolve()
    if not source.is_file():
        raise SystemExit("file not found")

    language = classify(source)
    task_id = f"cg-{int(time.time())}-{sha(source)[:12]}"
    work = INBOX / task_id
    work.mkdir(parents=True)
    working_copy = work / source.name
    shutil.copy2(source, working_copy)

    env_id = environment_identity()
    report = {
        "task_id": task_id,
        "owner_class": "USER_EVIDENCE",
        "origin_class": env_id["origin_class"],
        "execution_environment": env_id,
        "source_path": str(source),
        "source_sha256": sha(source),
        "language": language,
        "safety": safety_scan(working_copy),
        "passes": [],
    }

    if report["safety"]["status"] != "PASS":
        report["state"] = "REVIEW"
        output = REPORTS / (task_id + ".json")
        output.write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        return 3

    plateau = 0
    previous = None
    for index in range(MAX_PASSES):
        test_results = tests(working_copy, language)
        passed = all(item["returncode"] == 0 for item in test_results)
        improvement = {"changed": False, "actions": []}
        if not passed:
            improvement = deterministic_improve(working_copy, language)
        score = sum(1 for item in test_results if item["returncode"] == 0)
        signature = (score, sha(working_copy))
        plateau = plateau + 1 if signature == previous else 0
        previous = signature
        report["passes"].append(
            {
                "pass": index + 1,
                "tests": test_results,
                "improvement": improvement,
                "score": score,
                "sha256": sha(working_copy),
            }
        )
        if passed or plateau >= 1:
            break

    final_tests = tests(working_copy, language)
    qualified = all(item["returncode"] == 0 for item in final_tests)
    report["final_tests"] = final_tests
    report["qualified"] = qualified
    report["qualified_sha256"] = sha(working_copy)

    if qualified and not args.no_run:
        report["execution"] = execute(working_copy, language, args.arg, args.timeout)
        status = "PASS" if report["execution"]["returncode"] == 0 else "FAIL"
        report["verification"] = {
            "status": status,
            "basis": "process_returncode_plus_preexecution_qualification",
        }
    else:
        report["execution"] = {"skipped": True}
        report["verification"] = {
            "status": "PASS" if qualified else "FAIL",
            "basis": "qualification_only",
        }

    report["state"] = "COMPLETE" if report["verification"]["status"] == "PASS" else "FAILED"
    output = REPORTS / (task_id + ".json")
    output.write_text(json.dumps(report, indent=2))
    os.chmod(output, 0o600)
    evidence = EVID / (task_id + ".sha256")
    evidence.write_text(f"{sha(output)}  {output.name}\n")
    os.chmod(evidence, 0o600)
    print(json.dumps(report, indent=2))
    return 0 if report["verification"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
