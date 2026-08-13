from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

TOTAL_CYCLES = 100
SCHEMA = "wordbook-evolution-v1"


@dataclass(frozen=True)
class CycleSpec:
    cycle: int
    stage: str
    objective: str
    metric_keys: tuple[str, ...]


@dataclass(frozen=True)
class CorpusSnapshot:
    generation: int
    corpus_sha256: str
    parent_sha256: str | None
    encounter_count: int
    source_count: int
    canonical_entry_count: int

    def validate(self) -> None:
        if self.generation < 0:
            raise ValueError("generation must be non-negative")
        if len(self.corpus_sha256) != 64:
            raise ValueError("corpus_sha256 must be a SHA-256 hex digest")
        int(self.corpus_sha256, 16)
        if self.parent_sha256 is not None:
            if len(self.parent_sha256) != 64:
                raise ValueError("parent_sha256 must be a SHA-256 hex digest")
            int(self.parent_sha256, 16)
        for value in (
            self.encounter_count,
            self.source_count,
            self.canonical_entry_count,
        ):
            if value < 0:
                raise ValueError("corpus counts must be non-negative")


@dataclass(frozen=True)
class CycleEvidence:
    cycle: int
    stage: str
    objective: str
    input_sha256: str
    output_sha256: str
    metrics: dict[str, float]
    accepted: bool
    reasons: tuple[str, ...] = ()

    def digest(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class EvolutionLedger:
    baseline_sha256: str
    active_snapshot: CorpusSnapshot
    next_cycle: int = 1
    evidence_chain: list[str] = field(default_factory=list)
    status: str = "ACTIVE"

    def __post_init__(self) -> None:
        self.active_snapshot.validate()
        if self.active_snapshot.generation != 0 and not self.evidence_chain:
            raise ValueError("non-baseline snapshots require evidence lineage")
        if not 1 <= self.next_cycle <= TOTAL_CYCLES + 1:
            raise ValueError("next_cycle out of range")

    def advance(
        self,
        spec: CycleSpec,
        output: CorpusSnapshot,
        metrics: dict[str, float],
        *,
        regression: bool = False,
    ) -> CycleEvidence:
        before = self.active_snapshot
        output.validate()
        reasons: list[str] = []

        if self.status != "ACTIVE":
            reasons.append(f"ledger_not_active:{self.status}")
        if spec.cycle != self.next_cycle:
            reasons.append(f"out_of_order:expected={self.next_cycle}:observed={spec.cycle}")
        if before.generation != spec.cycle - 1:
            reasons.append("input_generation_not_bound_to_cycle")
        if output.generation != spec.cycle:
            reasons.append("output_generation_must_equal_cycle")
        if output.parent_sha256 != before.corpus_sha256:
            reasons.append("output_parent_does_not_match_active_corpus")
        if output.corpus_sha256 == before.corpus_sha256:
            reasons.append("cycle_produced_no_new_corpus_state")
        if output.encounter_count < before.encounter_count:
            reasons.append("encounter_history_regressed")
        if output.source_count < before.source_count:
            reasons.append("source_history_regressed")
        missing = [key for key in spec.metric_keys if key not in metrics]
        if missing:
            reasons.append(f"missing_metrics:{','.join(missing)}")
        if regression:
            reasons.append("explicit_regression_flag")

        accepted = not reasons
        evidence = CycleEvidence(
            cycle=spec.cycle,
            stage=spec.stage,
            objective=spec.objective,
            input_sha256=before.corpus_sha256,
            output_sha256=output.corpus_sha256,
            metrics=dict(metrics),
            accepted=accepted,
            reasons=tuple(reasons),
        )
        self.evidence_chain.append(evidence.digest())

        if accepted:
            self.active_snapshot = output
            self.next_cycle += 1
            if self.next_cycle == TOTAL_CYCLES + 1:
                self.status = "COMPLETE_100"
        else:
            self.status = "REVIEW_REQUIRED"
        return evidence


_STAGES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "01-corpus-integrity",
        (
            "Establish immutable encounter provenance for every captured token and phrase.",
            "Detect exact duplicate encounters without deleting source evidence.",
            "Detect near-duplicate source passages while preserving distinct provenance.",
            "Normalize source identifiers, timestamps, and capture channels.",
            "Repair broken source-to-encounter references and quarantine unresolved records.",
            "Measure corpus coverage by source, date, and capture pathway.",
            "Identify malformed text and encoding anomalies without rewriting originals.",
            "Create reversible canonicalization mappings for raw encounter text.",
            "Audit corpus deletions, merges, aliases, and reconstruction lineage.",
            "Freeze a reproducible generation-10 corpus integrity baseline.",
        ),
        ("provenance_coverage", "integrity_error_rate"),
    ),
    (
        "02-lexical-normalization",
        (
            "Improve token boundary detection across punctuation, apostrophes, and hyphenation.",
            "Improve case normalization while preserving proper-name and stylistic evidence.",
            "Improve lemma assignment with explicit ambiguity retention.",
            "Improve part-of-speech tagging using accumulated encounter context.",
            "Improve inflection-family grouping without collapsing distinct lexemes.",
            "Improve spelling-variant linking across dialect and historical forms.",
            "Improve abbreviation and acronym expansion with source-specific senses.",
            "Improve named-entity separation from ordinary vocabulary entries.",
            "Improve morphology decomposition into roots, affixes, and productive patterns.",
            "Calibrate lexical-normalization confidence and preserve unresolved alternatives.",
        ),
        ("normalization_accuracy", "ambiguity_preservation"),
    ),
    (
        "03-sense-modeling",
        (
            "Cluster encounters into candidate senses using contextual evidence.",
            "Separate homographs and unrelated etymological entries.",
            "Merge over-split senses only when corpus evidence supports equivalence.",
            "Attach definitions to senses rather than to surface forms alone.",
            "Rank senses by the user's observed encounter frequency.",
            "Detect source-domain-specific senses and technical meanings.",
            "Track sense drift across time and source communities.",
            "Represent unresolved polysemy as competing sense hypotheses.",
            "Improve sense-disambiguation confidence from accumulated corrections.",
            "Calibrate sense inventory quality against held-out encounter contexts.",
        ),
        ("sense_accuracy", "sense_calibration"),
    ),
    (
        "04-phrases-collocations",
        (
            "Discover repeated multiword expressions from accumulated encounters.",
            "Rank collocations by personal-corpus association strength.",
            "Distinguish compositional phrases from idioms and fixed expressions.",
            "Detect phrasal verbs and separable constructions.",
            "Detect discourse markers and formulaic sentence frames.",
            "Link compounds to component lexemes without erasing phrase meaning.",
            "Model preferred prepositions and argument patterns for learned words.",
            "Extract recurring adjective-noun and verb-object usage patterns.",
            "Identify source-specific jargon phrases and reusable terminology.",
            "Calibrate phrase recommendations using held-out corpus passages.",
        ),
        ("phrase_precision", "phrase_recall"),
    ),
    (
        "05-register-pragmatics",
        (
            "Infer formal, informal, technical, literary, and conversational register evidence.",
            "Infer politeness and interpersonal stance from observed contexts.",
            "Detect taboo, sensitive, archaic, regional, and marked usage evidence.",
            "Model connotation separately from denotation.",
            "Model rhetorical function such as emphasis, hedge, contrast, or dismissal.",
            "Detect genre-conditioned usage differences across the corpus.",
            "Track dialect and regional variants without imposing one as canonical.",
            "Improve usage-note generation from evidence-backed contrasts.",
            "Detect pragmatic mismatches in candidate example sentences.",
            "Calibrate register and pragmatics labels against accumulated corrections.",
        ),
        ("register_accuracy", "pragmatic_error_rate"),
    ),
    (
        "06-personal-language-model",
        (
            "Measure the user's observed vocabulary frequency distribution.",
            "Distinguish recognized vocabulary from actively produced vocabulary.",
            "Model recurring personal collocations and phrase preferences.",
            "Measure lexical diversity by source and writing context.",
            "Identify words repeatedly encountered but rarely retained.",
            "Identify words learned and subsequently used independently.",
            "Model personal confusion sets and frequently conflated senses.",
            "Model preferred definition depth and explanation granularity from interactions.",
            "Estimate personal familiarity without treating model confidence as user knowledge.",
            "Calibrate the personal-language profile against explicit user corrections.",
        ),
        ("personalization_gain", "familiarity_calibration"),
    ),
    (
        "07-graph-retrieval",
        (
            "Build lexical relations among lemmas, senses, phrases, and encounters.",
            "Improve synonym links with sense-level constraints.",
            "Improve antonym and contrast-set links with context evidence.",
            "Improve etymological and morphological relation navigation.",
            "Improve semantic-neighborhood retrieval from the accumulated corpus.",
            "Improve source-aware full-text retrieval and provenance display.",
            "Improve query expansion without hiding the user's exact search terms.",
            "Improve related-word ranking using personal relevance and corpus evidence.",
            "Detect graph contradictions, orphan nodes, and unsupported edges.",
            "Calibrate retrieval quality against a frozen query benchmark.",
        ),
        ("retrieval_quality", "unsupported_edge_rate"),
    ),
    (
        "08-learning-mastery",
        (
            "Generate recall prompts from authentic personal-corpus contexts.",
            "Generate cloze exercises with unambiguous answer evidence.",
            "Generate sense-contrast exercises for personal confusion sets.",
            "Generate morphology exercises grounded in observed word families.",
            "Generate collocation exercises grounded in personal encounters.",
            "Estimate forgetting risk from review history without fabricating mastery.",
            "Improve spaced-review scheduling from observed recall outcomes.",
            "Prioritize high-value weak vocabulary using frequency, utility, and difficulty.",
            "Detect exercise leakage, trivial cues, and ambiguous grading.",
            "Calibrate mastery estimates against held-out recall outcomes.",
        ),
        ("learning_gain", "mastery_calibration"),
    ),
    (
        "09-writing-assistance",
        (
            "Suggest learned vocabulary only when semantically appropriate to the draft.",
            "Detect misused learned words using sense and argument-pattern evidence.",
            "Detect register mismatches between proposed wording and writing context.",
            "Suggest personally underused but well-mastered vocabulary without forcing novelty.",
            "Suggest corpus-backed collocations and phrase completions.",
            "Explain why a proposed substitution changes meaning, tone, or implication.",
            "Detect repetition while preserving deliberate rhetorical repetition.",
            "Compare the user's draft with their own historical usage patterns.",
            "Measure whether writing suggestions preserve intended meaning after revision.",
            "Calibrate writing assistance against accepted and rejected suggestions.",
        ),
        ("suggestion_acceptance_quality", "meaning_preservation"),
    ),
    (
        "10-calibration-convergence",
        (
            "Audit every derived claim for a traceable corpus or dictionary evidence path.",
            "Recompute confidence calibration across lexical, sense, phrase, and register models.",
            "Stress-test the corpus against adversarially ambiguous words and contexts.",
            "Stress-test ingestion against malformed, duplicated, and contradictory sources.",
            "Measure regression against frozen benchmarks from earlier generations.",
            "Resolve or explicitly preserve contradictions discovered across model layers.",
            "Compress redundant derived state without deleting encounter provenance.",
            "Rebuild the complete corpus from raw encounters and verify reproducibility.",
            "Compare generation 99 against generation 0 and quantify cumulative improvement.",
            "Produce generation 100 with a complete lineage, evidence ledger, and unresolved-unknowns report.",
        ),
        ("global_calibration", "reproducibility", "cumulative_gain"),
    ),
)


def _build_cycle_specs() -> tuple[CycleSpec, ...]:
    specs: list[CycleSpec] = []
    cycle = 1
    for stage, objectives, metrics in _STAGES:
        if len(objectives) != 10:
            raise RuntimeError(f"stage {stage} must define exactly ten objectives")
        for objective in objectives:
            specs.append(
                CycleSpec(
                    cycle=cycle,
                    stage=stage,
                    objective=objective,
                    metric_keys=metrics,
                )
            )
            cycle += 1
    return tuple(specs)


CYCLE_SPECS = _build_cycle_specs()


def validate_cycle_schedule(specs: tuple[CycleSpec, ...] = CYCLE_SPECS) -> None:
    if len(specs) != TOTAL_CYCLES:
        raise ValueError("Wordbook requires exactly 100 successive cycles")
    cycles = [spec.cycle for spec in specs]
    if cycles != list(range(1, TOTAL_CYCLES + 1)):
        raise ValueError("cycles must be contiguous and ordered from 1 through 100")
    objectives = [spec.objective for spec in specs]
    if len(set(objectives)) != TOTAL_CYCLES:
        raise ValueError("every Wordbook cycle must have a distinct objective")
    stages = [spec.stage for spec in specs]
    ordered_stages = list(dict.fromkeys(stages))
    if len(ordered_stages) != 10:
        raise ValueError("Wordbook requires ten ordered stages")
    for stage in ordered_stages:
        if stages.count(stage) != 10:
            raise ValueError(f"stage {stage} must contain exactly ten cycles")


validate_cycle_schedule()
