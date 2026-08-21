import importlib
import json
import pathlib
import subprocess
import sys

REQUIRED_OUTPUTS = {
    "PROMPT_BOOTSTRAP.md",
    "PROJECT_BRIEF.md",
    "FEATURE_REGISTRY.json",
    "PRODUCT_ROADMAP.json",
    "MANIFEST.json",
}


def test_automation_platform_v1_end_to_end(tmp_path: pathlib.Path):
    run_task = importlib.import_module("centinal26.agent_execution_plane").run_task
    repo = pathlib.Path(__file__).resolve().parents[1]
    source = tmp_path / "project.md"
    output = tmp_path / "productized"
    source.write_text(
        "Goal: the project must produce a verified reusable automation agent workflow.\n"
        "The automation tool should turn project requirements into tested features.\n"
        "Validation passed when generated artifacts are independently verified.\n",
        encoding="utf-8",
    )

    productizer = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "project_productizer.py"),
            str(source),
            "-o",
            str(output),
        ],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    assert productizer.returncode == 0, productizer.stderr
    assert REQUIRED_OUTPUTS <= {path.name for path in output.iterdir()}

    features = json.loads((output / "FEATURE_REGISTRY.json").read_text(encoding="utf-8"))
    manifest = json.loads((output / "MANIFEST.json").read_text(encoding="utf-8"))
    prompt = (output / "PROMPT_BOOTSTRAP.md").read_text(encoding="utf-8")
    assert features
    assert manifest["protocol"]["canonical_v3_loaded"] is True
    assert manifest["protocol"]["sha256"]
    assert "Frost Master Project Protocol v3" in prompt

    verification_code = (
        "import json, pathlib; "
        f"root=pathlib.Path({str(output)!r}); "
        "m=json.loads((root/'MANIFEST.json').read_text()); "
        "f=json.loads((root/'FEATURE_REGISTRY.json').read_text()); "
        "assert m['protocol']['canonical_v3_loaded'] and len(f) >= 1"
    )
    judge_result = run_task(
        {
            "role": "judge",
            "command": [sys.executable, "-c", verification_code],
            "timeout": 60,
        },
        repo,
    )
    assert judge_result["status"] == "PASS"
    assert judge_result["evidence_digest"]
