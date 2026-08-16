from pathlib import Path
import re

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "termux"
    / "android_forensic_validation_campaign.sh"
)
TEXT = SCRIPT.read_text(encoding="utf-8")


def test_fail_closed_android_termux_identity():
    assert "*/com.termux/*" in TEXT
    assert "getprop ro.build.version.release" in TEXT


def test_forensic_acquisition_precedes_centinal_mutation():
    assert TEXT.index("frost_android_live_pre") < TEXT.index("centinal26_project_pre_reboot")
    assert "acquire android-live" in TEXT
    assert "frost_audit_pre" in TEXT
    assert "verify-package" in TEXT


def test_reuses_existing_physical_finalizer():
    assert "automation_project_finalizer.sh" in TEXT
    assert "centinal26_project_pre_reboot 20" in TEXT
    assert "centinal26_project_post_reboot 0" in TEXT


def test_no_automatic_reboot_command():
    for line in TEXT.splitlines():
        stripped = line.strip()
        assert not re.match(r"^(?:sudo\s+)?reboot(?:\s|$)", stripped)
        assert not stripped.startswith("termux-reboot")


def test_package_repair_requires_explicit_opt_in_and_never_bypasses_signatures():
    assert 'CENTINAL26_ALLOW_PACKAGE_REPAIR:-0' in TEXT
    lowered = TEXT.lower()
    assert "--allow-unauthenticated" not in lowered
    assert "trusted=yes" not in lowered
    assert "apt-key add" not in lowered


def test_campaign_identity_binds_commit_and_boot_epochs():
    assert 'git -C "$REPO_ROOT" rev-parse HEAD' in TEXT
    assert "pre_boot_id" in TEXT
    assert "post_boot_id" in TEXT
    assert "repository HEAD changed across reboot" in TEXT


def test_receipts_are_hash_sealed_and_non_promoting():
    assert "PAYLOAD_SHA256SUMS.txt" in TEXT
    assert "campaign_receipt.json.sha256" in TEXT
    assert "promotion_authority:false" in TEXT
    assert "CAMPAIGN_VALIDATED" in TEXT


def test_package_state_is_captured_before_and_after_mutation_points():
    assert "package_state_pre" in TEXT
    assert "package_state_after_centinal" in TEXT
    assert "package_state_post" in TEXT
    assert "apt-sources.txt" in TEXT
    assert "termux-keyring" in TEXT
    assert "DEPRECATED_OR_LEGACY_SOURCE_DETECTED" in TEXT
