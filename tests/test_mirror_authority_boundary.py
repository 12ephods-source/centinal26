from pathlib import Path


ENTITY_NAMES = ("AutomationRoleResult", "AutomationVerificationVerdict")
PRODUCTION_ROOTS = (Path("src"), Path("scripts"), Path("termux"))
ALLOWED_PATHS = {Path("src/centinal26/mirror_evidence.py")}


def test_mutable_base44_evidence_has_no_direct_production_authority_consumer():
    violations: list[str] = []
    for root in PRODUCTION_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path in ALLOWED_PATHS:
                continue
            if path.suffix not in {".py", ".sh", ".js", ".ts", ".yml", ".yaml"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(entity_name in text for entity_name in ENTITY_NAMES):
                violations.append(str(path))

    assert violations == [], (
        "mutable Base44 evidence entities must be consumed only through the "
        f"canonical binding gate; direct references found in: {violations}"
    )
