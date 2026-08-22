import hashlib
import json
from dataclasses import dataclass

TRUSTED_BASELINE_SOURCES = {"trusted_git", "package_manifest", "vendor_hash", "known_good_backup"}
FORBIDDEN_CAPABILITIES = {"unrestricted_shell", "credential_export", "disable_verification", "bypass_authorization"}


def _sha256_text(value):
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class SecurityDecision:
    allowed: bool
    checks: dict
    reasons: tuple
    context_hash: str


class SecurityPolicy:
    """Fail-closed security policy for persistent automation qualification.

    Security assertions are derived from evidence-bearing context rather than
    caller-supplied qualification booleans. The policy intentionally separates
    authority, capability, execution, verification, provenance, device origin,
    and epistemic claim status.
    """

    def evaluate(self, context):
        context = dict(context or {})
        capabilities = set(context.get("capabilities", []))
        baseline = dict(context.get("baseline", {}))
        device = dict(context.get("device", {}))
        claim = dict(context.get("claim", {}))

        baseline_expected = baseline.get("expected_sha256")
        baseline_actual = baseline.get("actual_sha256")
        trusted_provenance = (
            baseline.get("source") in TRUSTED_BASELINE_SOURCES
            and bool(baseline_expected)
            and baseline_expected == baseline_actual
        )

        device_claimed = bool(device.get("claimed"))
        device_origin = str(device.get("origin", "")).upper()
        device_claim_valid = (
            not device_claimed
            or (
                ("ANDROID" in device_origin or "TERMUX" in device_origin)
                and bool(device.get("report_sha256"))
                and bool(device.get("origin_verified"))
            )
        )

        claim_status = str(claim.get("status", "UNKNOWN")).upper()
        claim_source = str(claim.get("source", "unknown")).lower()
        epistemic_valid = not (
            claim_status == "OBSERVED" and claim_source in {"model", "ai", "llm", "inference"}
        )

        destructive = bool(context.get("destructive_action"))
        destructive_ok = not destructive or bool(context.get("destructive_authorized"))

        checks = {
            "authority_verified": bool(context.get("authority_verified")),
            "capability_authorized": bool(context.get("capability_authorized")),
            "bounded_execution": bool(context.get("bounded_execution")),
            "independent_verification": bool(context.get("independent_verification")),
            "evidence_chain_valid": bool(context.get("evidence_chain_valid")),
            "trusted_provenance": trusted_provenance,
            "device_claim_valid": device_claim_valid,
            "epistemic_claim_valid": epistemic_valid,
            "no_forbidden_capability": not bool(capabilities & FORBIDDEN_CAPABILITIES),
            "no_secret_exposure": not bool(context.get("secret_exposure")),
            "destructive_action_authorized": destructive_ok,
        }
        reasons = tuple(key for key, value in checks.items() if not value)
        canonical = json.dumps(context, sort_keys=True, separators=(",", ":"))
        return SecurityDecision(
            allowed=all(checks.values()),
            checks=checks,
            reasons=reasons,
            context_hash=_sha256_text(canonical),
        )
