from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "termux"
    / "termux_repository_recovery.sh"
)
TEXT = SCRIPT.read_text(encoding="utf-8")


def test_recovery_requires_real_termux_environment():
    assert "*/com.termux/*" in TEXT
    assert "getprop ro.build.version.release" in TEXT


def test_repair_requires_explicit_mutation_authority():
    assert "CENTINAL26_ALLOW_PACKAGE_REPAIR:-0" in TEXT
    assert "repository mutation requires CENTINAL26_ALLOW_PACKAGE_REPAIR=1" in TEXT
    assert "repository rollback requires CENTINAL26_ALLOW_PACKAGE_REPAIR=1" in TEXT


def test_normalizes_to_current_official_primary_main_source():
    assert "deb https://packages.termux.dev/apt/termux-main stable main" in TEXT
    assert "CENTINAL26_DISABLED_MAIN_SOURCE" in TEXT
    assert "normalize_main_sources" in TEXT


def test_detects_legacy_and_duplicate_source_conditions():
    assert "termux\\.net" in TEXT
    assert "packages\\.termux\\.org" in TEXT
    assert "dl\\.bintray\\.com" in TEXT
    assert "active_termux_main_sources" in TEXT
    assert "legacy_active_sources" in TEXT


def test_no_signature_bypass_or_implicit_key_import():
    lowered = TEXT.lower()
    assert "--allow-unauthenticated" not in lowered
    assert "trusted=yes" not in lowered
    assert "apt-key add" not in lowered
    assert "gpg --import" not in lowered
    assert "no key was imported" in lowered
    assert "no signature check was bypassed" in lowered


def test_known_missing_autobuild_key_is_classified_separately():
    assert "5A897D96E57CF20C" in TEXT
    assert "NO_PUBKEY" in TEXT
    assert "trust-anchor failure, not a mirror-selection failure" in TEXT


def test_source_mutation_has_preserved_rollback_snapshot():
    assert "source-backup/etc/apt" in TEXT
    assert "backup_sources" in TEXT
    assert "restore_sources" in TEXT
    assert "--rollback <repair-dir>" in TEXT


def test_keyring_is_refreshed_only_after_authenticated_update():
    first_update = TEXT.index('pkg update -y > "$out/pkg-update.stdout.txt"')
    keyring_install = TEXT.index("pkg install -y termux-keyring termux-tools")
    verify_update = TEXT.index('pkg update -y > "$out/pkg-update-verify.stdout.txt"')
    assert first_update < keyring_install < verify_update


def test_evidence_is_captured_before_normalization_and_after_outcome():
    assert 'capture_state "$out/before"' in TEXT
    assert 'capture_state "$out/normalized"' in TEXT
    assert 'capture_state "$out/after"' in TEXT
    assert "SHA256SUMS.txt" in TEXT
