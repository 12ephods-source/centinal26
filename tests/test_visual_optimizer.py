from centinal26.visual_optimizer import Candidate, Defect, Policy, Scores, VisualOptimizer, accepted


def test_acceptance_gate():
    p = Policy()
    assert accepted(Scores(.95, .10, .02), p)
    assert not accepted(Scores(.80, .50, .01), p)
    assert not accepted(Scores(.99, .00, .00), p)
    assert not accepted(Scores(.99, .20, .20), p)


class FakeProvider:
    def __init__(self):
        self.parents = []
        self.i = 0

    def generate(self, *, canonical_artifact, defect, locks):
        self.parents.append(canonical_artifact)
        self.i += 1
        return f"candidate-{self.i}"

    def evaluate(self, *, canonical_artifact, candidate_artifact, defect, locks):
        # First candidate regresses preservation and must not become the next parent.
        if candidate_artifact == "candidate-1":
            scores = Scores(.50, .90, .01)
        else:
            scores = Scores(.98, .20, .01)
        return Candidate(candidate_artifact, scores, {"checked": True})


def test_rejected_candidate_never_becomes_parent(tmp_path):
    provider = FakeProvider()
    defects = (Defect("a", "a"), Defect("b", "b"))
    optimizer = VisualOptimizer(provider, tmp_path / "ledger.jsonl")
    result = optimizer.optimize("canonical-master", defects=defects, locks=("foreground",))
    assert provider.parents == ["canonical-master", "canonical-master"]
    assert result == "candidate-2"
    lines = (tmp_path / "ledger.jsonl").read_text().splitlines()
    assert len(lines) == 2
    assert '"decision": "REJECT"' in lines[0]
    assert '"decision": "PROMOTE"' in lines[1]
