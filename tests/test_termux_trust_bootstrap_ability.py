from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "deploy"
    / "termux"
    / "FROST_TERMUX_TRUST_BOOTSTRAP_v1.0.sh"
)
TEXT = SCRIPT.read_text(encoding="utf-8")


def test_trust_bootstrap_requires_real_termux_and_separate_authority() -> None:
    assert "*/com.termux/*" in TEXT
    assert "getprop ro.build.version.release" in TEXT
    assert "FROST_ALLOW_TRUST_BOOTSTRAP:-0" in TEXT
    assert "trust-root mutation requires FROST_ALLOW_TRUST_BOOTSTRAP=1" in TEXT
    assert "trust-root rollback requires FROST_ALLOW_TRUST_BOOTSTRAP=1" in TEXT


def test_pins_exact_official_termux_commit_blob_and_full_fingerprint() -> None:
    assert "da8b07830fd2049bc4df6119befceb565732e36b" in TEXT
    assert "c5ed76a1b9a1f2bc2e296bdd5ca50cf1f1f12706" in TEXT
    assert "CC72CF8BA7DBFA0182877D045A897D96E57CF20C" in TEXT
    assert "5A897D96E57CF20C" in TEXT
    assert "raw.githubusercontent.com/termux/termux-packages" in TEXT


def test_payload_is_verified_by_git_blob_and_openpgp_fingerprint_before_write() -> None:
    verify_index = TEXT.index('verify_payload "$downloaded"')
    install_index = TEXT.index('install -m 600 "$downloaded" "$SHARE_KEY"')
    assert verify_index < install_index
    assert "git hash-object" in TEXT
    assert "gpg --batch --quiet --show-keys --with-colons" in TEXT
    assert 'actual_blob="$(git_blob "$file")"' in TEXT
    assert 'actual_fingerprint="$(key_fingerprint "$file")"' in TEXT


def test_download_is_https_only_and_does_not_use_keyservers() -> None:
    lowered = TEXT.lower()
    assert "curl -fl --proto '=https' --tlsv1.2" in lowered
    assert "recv-key" not in lowered
    assert "keyserver" not in lowered
    assert "wget" not in lowered


def test_bootstrap_never_disables_apt_signature_verification() -> None:
    lowered = TEXT.lower()
    assert "--allow-unauthenticated" not in lowered
    assert "trusted=yes" not in lowered
    assert "apt-key" not in lowered
    assert "gpg --import" not in lowered
    assert "apt signature verification remains authoritative" in lowered


def test_bootstrap_preserves_rollback_and_restores_on_failed_postwrite_check() -> None:
    assert "backup_existing" in TEXT
    assert "restore_backup" in TEXT
    assert "share.present" in TEXT
    assert "apt.present" in TEXT
    assert "previous trust state restored" in TEXT
    assert "--rollback <bootstrap-dir>" in TEXT


def test_bootstrap_writes_only_the_pinned_autobuild_anchor() -> None:
    assert 'install -m 600 "$downloaded" "$SHARE_KEY"' in TEXT
    assert 'ln -sfn "$SHARE_KEY" "$APT_KEY"' in TEXT
    assert "termux-autobuilds.gpg" in TEXT
    assert "termux-pacman.gpg" not in TEXT


def test_doctor_requires_blob_fingerprint_and_apt_symlink() -> None:
    assert 'verify_payload "$SHARE_KEY"' in TEXT
    assert 'readlink "$APT_KEY"' in TEXT
    assert "BLOCKED_TRUST_ANCHOR_IDENTITY" in TEXT
    assert "BLOCKED_APT_TRUST_PATH" in TEXT


def test_evidence_is_captured_before_after_and_sha256_sealed() -> None:
    assert 'capture_state "$out/before"' in TEXT
    assert 'capture_state "$out/after"' in TEXT
    assert "downloaded.sha256" in TEXT
    assert "downloaded.git-blob-sha" in TEXT
    assert "downloaded.fingerprint" in TEXT
    assert "SHA256SUMS.txt" in TEXT


def test_semantic_acceptance_is_deferred_to_authenticated_repository_recovery() -> None:
    assert "FROST_TERMUX_REPOSITORY_RECOVERY_v1.0.sh --repair" in TEXT
    assert "pkg update" not in TEXT
    assert "pkg install" not in TEXT
