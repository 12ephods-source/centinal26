from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "termux" / "termux_trust_bootstrap.sh"
TEXT = SCRIPT.read_text(encoding="utf-8")


def test_trust_mutation_requires_distinct_explicit_authority():
    assert "CENTINAL26_ALLOW_TRUST_BOOTSTRAP:-0" in TEXT
    assert "--bootstrap" in TEXT


def test_bootstrap_is_pinned_to_exact_official_termux_identity():
    assert "termux/termux-packages" in TEXT
    assert "da8b07830fd2049bc4df6119befceb565732e36b" in TEXT
    assert "c5ed76a1b9a1f2bc2e296bdd5ca50cf1f1f12706" in TEXT
    assert "5A897D96E57CF20C" in TEXT
    assert "git hash-object" in TEXT


def test_bootstrap_does_not_disable_signature_verification_or_use_keyservers():
    lowered = TEXT.lower()
    assert "--allow-unauthenticated" not in lowered
    assert "trusted=yes" not in lowered
    assert "apt-key" not in lowered
    assert "recv-key" not in lowered
    assert "keyserver" not in lowered


def test_bootstrap_preserves_before_after_evidence_and_existing_anchor():
    assert 'capture_state "$out/before"' in TEXT
    assert 'capture_state "$out/after"' in TEXT
    assert "backup/share-termux-autobuilds.gpg" in TEXT
    assert "SHA256SUMS.txt" in TEXT


def test_bootstrap_only_installs_the_pinned_autobuild_anchor():
    assert 'install -m 600 "$downloaded" "$SHARE_KEY"' in TEXT
    assert 'ln -sfn "$SHARE_KEY" "$APT_KEY"' in TEXT
    assert "termux-autobuilds.gpg" in TEXT


def test_bootstrap_defers_semantic_acceptance_to_authenticated_apt_recovery():
    assert "APT signature verification remains authoritative" in TEXT
    assert "repository recovery --repair" in TEXT
