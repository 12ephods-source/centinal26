from centinal26.claim_verifier import (
    Claim,
    Evidence,
    EvidenceTier,
    Verdict,
    atomic_claims,
    evaluate,
)


def test_document_is_not_independent_verification():
    claim = Claim("C1", "Millions of simulations were run.", claim_type="activity")
    evidence = [
        Evidence(
            "manuscript",
            "A project manuscript states that millions of simulations were run.",
            EvidenceTier.AUTHORED_DOCUMENT,
            supports=True,
        )
    ]
    result = evaluate(claim, evidence)
    assert result.verdict == Verdict.DOCUMENTED_ONLY


def test_primary_external_evidence_can_verify():
    claim = Claim("C2", "A public platform recorded 995000 views.", claim_type="metric")
    evidence = [
        Evidence(
            "platform-export",
            "Signed platform analytics export records 995000 views.",
            EvidenceTier.PRIMARY_EXTERNAL,
            supports=True,
            independent=True,
        )
    ]
    result = evaluate(claim, evidence)
    assert result.verdict == Verdict.VERIFIED


def test_reproducible_computation_is_partial_without_external_validation():
    claim = Claim("C3", "The solver returns r=0.09081.", claim_type="computational")
    evidence = [
        Evidence(
            "rerun",
            "Independent deterministic rerun reproduces r=0.09081.",
            EvidenceTier.REPRODUCIBLE_EXECUTION,
            supports=True,
            reproducible=True,
        )
    ]
    result = evaluate(claim, evidence)
    assert result.verdict == Verdict.PARTIALLY_VERIFIED


def test_stronger_adverse_evidence_contradicts():
    claim = Claim("C4", "Beta equals 1e-15 when derived from the GUT scale.")
    evidence = [
        Evidence(
            "old-draft",
            "Earlier draft states beta=1e-15.",
            EvidenceTier.AUTHORED_DOCUMENT,
            supports=True,
        ),
        Evidence(
            "corrected-rerun",
            "Corrected arithmetic gives beta about 3.96e-6.",
            EvidenceTier.REPRODUCIBLE_EXECUTION,
            supports=False,
            reproducible=True,
        ),
    ]
    result = evaluate(claim, evidence)
    assert result.verdict == Verdict.CONTRADICTED


def test_predictions_are_not_misclassified_as_facts():
    claim = Claim("C5", "A future experiment will detect the signal.", prediction=True)
    result = evaluate(claim, [])
    assert result.verdict == Verdict.PREDICTION


def test_atomic_claim_extraction_preserves_wording():
    text = "I wrote the solver. I ran simulations; the result was recorded."
    claims = atomic_claims(text)
    assert [c.text for c in claims] == [
        "I wrote the solver.",
        "I ran simulations",
        "the result was recorded.",
    ]
