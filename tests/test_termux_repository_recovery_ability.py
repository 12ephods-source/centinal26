from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "deploy"
    / "termux"
    / "FROST_TERMUX_REPOSITORY_RECOVERY_v1.0.sh"
)
TEXT = SCRIPT.read_text(encoding="utf-8")


def test_recovery_requires_real_termux_environment() -> None:
    assert "*/com.termux/*" in TEXT
    assert "getprop ro.build.version.release" in TEXT


def test_repair_and_rollback_require_explicit_mutation_authority() -> None:
    assert "FROST_ALLOW_PACKAGE_REPAIR:-0" in TEXT
    assert "repository mutation requires FROST_ALLOW_PACKAGE_REPAIR=1" in TEXT
    assert "repository rollback requires FROST_ALLOW_PACKAGE_REPAIR=1" in TEXT


def test_prefers_current_upstream_default_main_source() -> None:
    assert "deb https://packages-cf.termux.dev/apt/termux-main/ stable main" in TEXT
    assert "https://packages.termux.dev/apt/termux-main/" in TEXT


def test_only_normalizes_termux_main_not_root_or_x11() -> None:
    assert '[[ "$line" != *"termux-root"* ]]' in TEXT
    assert '[[ "$line" != *"termux-x11"* ]]' in TEXT
    assert "FROST_DISABLED_TERMUX_MAIN_SOURCE" in TEXT


def test_deb822_main_sources_fail_closed_instead_of_being_rewritten() -> None:
    assert "termux_main_deb822_files" in TEXT
    assert "this version will not rewrite .sources files" in TEXT
    assert "preserve it and use termux-change-repo/manual review" in TEXT


def test_no_signature_bypass_or_unverified_key_import() -> None:
    lowered = TEXT.lower()
    assert "--allow-unauthenticated" not in lowered
    assert "trusted=yes" not in lowered
    assert "apt-key add" not in lowered
    assert "gpg --import" not in lowered
    assert "no key was imported" in lowered
    assert "no signature check was bypassed" in lowered


def test_known_missing_autobuild_key_is_classified_separately() -> None:
    assert "5A897D96E57CF20C" in TEXT
    assert "NO_PUBKEY" in TEXT
    assert "Trust-root recovery remains a separate verification boundary." in TEXT


def test_source_mutation_has_preserved_rollback_snapshot() -> None:
    assert "source-backup/etc/apt" in TEXT
    assert "backup_sources" in TEXT
    assert "restore_sources" in TEXT
    assert "--rollback <repair-dir>" in TEXT


def test_failed_update_restores_original_source_configuration() -> None:
    assert "rollback_after_failure" in TEXT
    assert 'capture_state "$out/after-source-rollback"' in TEXT
    assert "source configuration was restored" in TEXT


def test_keyring_refresh_only_follows_authenticated_update() -> None:
    first_update = TEXT.index('pkg update -y > "$out/pkg-update.stdout.txt"')
    keyring_install = TEXT.index("pkg install -y termux-keyring termux-tools")
    verify_update = TEXT.index('pkg update -y > "$out/pkg-update-verify.stdout.txt"')
    assert first_update < keyring_install < verify_update


def test_evidence_is_captured_and_sha256_sealed() -> None:
    assert 'capture_state "$out/before"' in TEXT
    assert 'capture_state "$out/normalized"' in TEXT
    assert 'capture_state "$out/after"' in TEXT
    assert "SHA256SUMS.txt" in TEXT


def test_repair_does_not_auto_invoke_trust_bootstrap() -> None:
    assert "CENTINAL26_ALLOW_TRUST_BOOTSTRAP" not in TEXT
    assert "termux_trust_bootstrap" not in TEXT.lower()
