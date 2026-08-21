from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
PHYSICAL_SOURCE = "9c0925ee7e3dc23f6e81718f9c1a2ca7926ec483"


def test_readme_uses_current_canonical_identity_and_state():
    assert README.startswith("# Automation OS — Frost Forge")
    assert "Canonical product name: `Frost Forge` / `Automation OS`." in README
    assert "Automation Platform v1 host | `VERIFIED_COMPLETE`" in README
    assert "Physical Android/Termux | `BLOCKED_EXTERNAL_PHYSICAL_EVIDENCE`" in README
    assert PHYSICAL_SOURCE in README
    assert "GitHub issue #208 is the canonical Android/Termux qualification tracker." in README


def test_legacy_names_and_release_records_are_compatibility_not_current_truth():
    assert "former human-facing name: `Wazoo26`" in README
    assert "Historical recovery/bootstrap state" in README
    assert "Historical recoverable release target" in README
    assert "Historical issue #64, RC9, RC3/RC4 finalizers" in README
    assert "They do not replace issue #208 as the current physical acceptance path." in README
