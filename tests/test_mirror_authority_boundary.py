from pathlib import Path

ENTITY_NAMES = ("AutomationRoleResult", "AutomationVerificationVerdict")
PRODUCTION_ROOTS = (Path("src"), Path("scripts"), Path("termux"))
MIRROR_GATE = Path("src/centinal26/mirror_evidence.py")
PROVIDER_WRITER = Path("src/centinal26/provider_bridge.py")
ALLOWED_PATHS = {MIRROR_GATE, PROVIDER_WRITER}


def test_mutable_base44_evidence_has_no_unregistered_production_authority_consumer():
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
        "mutable Base44 evidence entities may appear only in the canonical binding gate "
        "or the registered non-authoritative provider writer; direct references found "
        f"in: {violations}"
    )


def test_registered_provider_writer_requires_canonical_authority_separate_from_mirror():
    text = PROVIDER_WRITER.read_text(encoding="utf-8")
    required = (
        "canonical_mirror_projection",
        "mirror_record_hash",
        "verify_provider_authority",
        "provider_mutation_grant",
        'event.type != "DECISION_RECORDED"',
        "provider_authority_grant_not_allow",
    )
    for marker in required:
        assert marker in text

    # The mutable Base44 row is staging/evidence only. The bridge's authority proof is
    # independently rooted in the append-only canonical event store.
    assert "subject=spec.authority.identity" in text
    assert 'source="canonical-event-store"' in text
    assert "External Centinal26 code must not embed an admin password" in text
