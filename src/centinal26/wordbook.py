from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Iterable, Iterator, Sequence

SCHEMA_VERSION = "centinal26-wordbook-v1"
WORD_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)


class Attribution(StrEnum):
    USER_DIRECT = "USER_DIRECT"
    QUOTED = "QUOTED"
    AI_GENERATED = "AI_GENERATED"
    AI_ACCEPTED = "AI_ACCEPTED"
    AI_REJECTED = "AI_REJECTED"
    META_REFERENCE = "META_REFERENCE"
    OTHER = "OTHER"


@dataclass(frozen=True)
class SourceIdentity:
    source_type: str
    external_id: str
    authored_by: str
    created_at: str | None
    content_sha256: str


@dataclass(frozen=True)
class QueryResult:
    term: str
    authored_total: int
    ordinary_usage: int
    meta_reference: int
    quoted_usage: int
    ai_generated: int
    ai_accepted: int
    ai_rejected: int
    evidence_ids: tuple[int, ...]


@dataclass(frozen=True)
class EvolutionPolicy:
    min_phrase_n: int = 2
    max_phrase_n: int = 8
    min_phrase_count: int = 2
    recent_weight: float = 0.25
    rejection_penalty: float = 1.0
    meta_penalty: float = 0.5

    def validate(self) -> "EvolutionPolicy":
        if not 1 <= self.min_phrase_n <= self.max_phrase_n <= 12:
            raise ValueError("phrase n-gram bounds must satisfy 1 <= min <= max <= 12")
        if self.min_phrase_count < 1:
            raise ValueError("min_phrase_count must be >= 1")
        for name in ("recent_weight", "rejection_penalty", "meta_penalty"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 2.0:
                raise ValueError(f"{name} must be in [0,2]")
        return self


@dataclass(frozen=True)
class EvolutionGeneration:
    generation: int
    phase: str
    baseline_score: float
    candidate_score: float
    promoted: bool
    policy_before_sha256: str
    policy_after_sha256: str
    evidence_sha256: str


@dataclass(frozen=True)
class EvolutionReport:
    schema: str
    generations: int
    promoted_generations: int
    rejected_generations: int
    initial_policy: EvolutionPolicy
    final_policy: EvolutionPolicy
    records: tuple[EvolutionGeneration, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "generations": self.generations,
            "promoted_generations": self.promoted_generations,
            "rejected_generations": self.rejected_generations,
            "initial_policy": asdict(self.initial_policy),
            "final_policy": asdict(self.final_policy),
            "records": [asdict(record) for record in self.records],
        }


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def content_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tokenize(text: str) -> list[str]:
    return [match.group(0).casefold().replace("’", "'") for match in WORD_RE.finditer(text)]


def ngrams(tokens: Sequence[str], n: int) -> Iterator[str]:
    if n < 1:
        raise ValueError("n must be >= 1")
    for i in range(0, len(tokens) - n + 1):
        yield " ".join(tokens[i : i + n])


def classify_occurrence(text: str, match: re.Match[str], token: str) -> Attribution:
    """Conservatively separate direct usage from quotation and meta-discussion."""
    sentence_left = max(
        text.rfind(".", 0, match.start()),
        text.rfind("?", 0, match.start()),
        text.rfind("!", 0, match.start()),
    ) + 1
    candidates = [
        pos
        for pos in (
            text.find(".", match.end()),
            text.find("?", match.end()),
            text.find("!", match.end()),
        )
        if pos != -1
    ]
    sentence_right = min(candidates) if candidates else len(text)
    sentence = text[sentence_left:sentence_right]
    relative_start = match.start() - sentence_left
    for opener, closer in (("\"", "\""), ("'", "'"), ("“", "”"), ("‘", "’")):
        before = sentence[:relative_start].rfind(opener)
        after = sentence[relative_start + len(match.group(0)) :].find(closer)
        if before != -1 and after != -1:
            return Attribution.QUOTED

    left = text[max(0, match.start() - 120) : match.start()]
    right = text[match.end() : min(len(text), match.end() + 40)]
    context = f"{left}{token}{right}"
    escaped = re.escape(token)
    meta_patterns = (
        rf"\b(?:word|phrase|term)\s+[\"'“‘]?{escaped}[\"'”’]?\b",
        rf"\b(?:say|says|said|use|uses|used|using)\b[^.!?\n]{{0,80}}\b{escaped}\b",
        rf"\b(?:call|calls|called|name|named)\b[^.!?\n]{{0,80}}\b{escaped}\b",
    )
    if any(re.search(pattern, context, re.IGNORECASE) for pattern in meta_patterns):
        return Attribution.META_REFERENCE
    return Attribution.USER_DIRECT


class WordbookStore:
    """Local-first immutable observation store for personal-language evidence."""

    def __init__(self, database: str | Path = ":memory:") -> None:
        self.path = str(database)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "WordbookStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        self.close()

    def _create_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY,
                source_type TEXT NOT NULL,
                external_id TEXT NOT NULL,
                authored_by TEXT NOT NULL,
                created_at TEXT,
                content_sha256 TEXT NOT NULL,
                content TEXT NOT NULL,
                UNIQUE(source_type, external_id, content_sha256)
            );

            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY,
                source_id INTEGER NOT NULL REFERENCES sources(id),
                ordinal INTEGER NOT NULL,
                token TEXT NOT NULL,
                attribution TEXT NOT NULL,
                start_char INTEGER NOT NULL,
                end_char INTEGER NOT NULL,
                UNIQUE(source_id, ordinal, attribution)
            );

            CREATE INDEX IF NOT EXISTS idx_observation_token
                ON observations(token, attribution);
            CREATE INDEX IF NOT EXISTS idx_observation_source
                ON observations(source_id, ordinal);

            CREATE TABLE IF NOT EXISTS phrases (
                id INTEGER PRIMARY KEY,
                source_id INTEGER NOT NULL REFERENCES sources(id),
                n INTEGER NOT NULL,
                ordinal INTEGER NOT NULL,
                phrase TEXT NOT NULL,
                attribution TEXT NOT NULL,
                UNIQUE(source_id, n, ordinal, attribution)
            );

            CREATE INDEX IF NOT EXISTS idx_phrase_phrase
                ON phrases(phrase, attribution);

            CREATE TABLE IF NOT EXISTS rejections (
                id INTEGER PRIMARY KEY,
                normalized_text TEXT NOT NULL UNIQUE,
                reason TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS evolution_runs (
                id INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                report_sha256 TEXT NOT NULL,
                report_json TEXT NOT NULL
            );
            """
        )
        try:
            self.conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS source_fts USING fts5(content, content='sources', content_rowid='id')"
            )
            self.conn.executescript(
                """
                CREATE TRIGGER IF NOT EXISTS sources_ai AFTER INSERT ON sources BEGIN
                    INSERT INTO source_fts(rowid, content) VALUES (new.id, new.content);
                END;
                CREATE TRIGGER IF NOT EXISTS sources_ad AFTER DELETE ON sources BEGIN
                    INSERT INTO source_fts(source_fts, rowid, content)
                    VALUES('delete', old.id, old.content);
                END;
                CREATE TRIGGER IF NOT EXISTS sources_au AFTER UPDATE ON sources BEGIN
                    INSERT INTO source_fts(source_fts, rowid, content)
                    VALUES('delete', old.id, old.content);
                    INSERT INTO source_fts(rowid, content) VALUES (new.id, new.content);
                END;
                """
            )
        except sqlite3.OperationalError:
            pass
        self.conn.commit()

    def ingest_text(
        self,
        *,
        text: str,
        source_type: str,
        external_id: str,
        authored_by: str = "user",
        created_at: str | None = None,
        attribution: Attribution = Attribution.USER_DIRECT,
        max_phrase_n: int = 8,
    ) -> SourceIdentity:
        digest = content_sha256(text)
        self.conn.execute(
            """
            INSERT OR IGNORE INTO sources
                (source_type, external_id, authored_by, created_at, content_sha256, content)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (source_type, external_id, authored_by, created_at, digest, text),
        )
        inserted = bool(self.conn.execute("SELECT changes()").fetchone()[0])
        row = self.conn.execute(
            """
            SELECT id FROM sources
            WHERE source_type = ? AND external_id = ? AND content_sha256 = ?
            """,
            (source_type, external_id, digest),
        ).fetchone()
        if row is None:
            raise RuntimeError("source insert/select consistency failure")
        source_id = int(row["id"])
        if inserted:
            matches = list(WORD_RE.finditer(text))
            normalized = [m.group(0).casefold().replace("’", "'") for m in matches]
            occurrence_attributions: list[Attribution] = []
            for ordinal, (match, token) in enumerate(zip(matches, normalized, strict=True)):
                observed_attribution = (
                    classify_occurrence(text, match, token)
                    if attribution is Attribution.USER_DIRECT
                    else attribution
                )
                occurrence_attributions.append(observed_attribution)
                self.conn.execute(
                    """
                    INSERT INTO observations
                        (source_id, ordinal, token, attribution, start_char, end_char)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        ordinal,
                        token,
                        observed_attribution.value,
                        match.start(),
                        match.end(),
                    ),
                )
            upper = min(max_phrase_n, len(normalized))
            for n in range(2, upper + 1):
                for ordinal, phrase in enumerate(ngrams(normalized, n)):
                    window = occurrence_attributions[ordinal : ordinal + n]
                    phrase_attribution = attribution
                    if attribution is Attribution.USER_DIRECT:
                        if Attribution.META_REFERENCE in window:
                            phrase_attribution = Attribution.META_REFERENCE
                        elif Attribution.QUOTED in window:
                            phrase_attribution = Attribution.QUOTED
                        else:
                            phrase_attribution = Attribution.USER_DIRECT
                    self.conn.execute(
                        """
                        INSERT INTO phrases
                            (source_id, n, ordinal, phrase, attribution)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (source_id, n, ordinal, phrase, phrase_attribution.value),
                    )
            self.conn.commit()
        return SourceIdentity(source_type, external_id, authored_by, created_at, digest)

    def ingest_chatgpt_export(
        self,
        path: str | Path,
        *,
        user_author_names: Iterable[str] = ("user",),
    ) -> dict[str, int]:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("ChatGPT conversations.json must contain a top-level list")
        accepted_names = {name.casefold() for name in user_author_names}
        stats: Counter[str] = Counter()
        seen_messages: set[str] = set()

        for conversation in payload:
            if not isinstance(conversation, dict):
                continue
            conversation_id = str(
                conversation.get("id") or conversation.get("conversation_id") or "unknown"
            )
            mapping = conversation.get("mapping")
            if not isinstance(mapping, dict):
                continue
            for node_id, node in mapping.items():
                if not isinstance(node, dict):
                    continue
                message = node.get("message")
                if not isinstance(message, dict):
                    continue
                author = message.get("author") or {}
                role = str(author.get("role") or "").casefold() if isinstance(author, dict) else ""
                name = str(author.get("name") or "").casefold() if isinstance(author, dict) else ""
                is_user = role == "user" or name in accepted_names
                if not is_user:
                    stats["non_user_messages"] += 1
                    continue
                content = message.get("content") or {}
                parts = content.get("parts") if isinstance(content, dict) else None
                if not isinstance(parts, list):
                    continue
                text = "\n".join(part for part in parts if isinstance(part, str)).strip()
                if not text:
                    continue
                message_id = str(message.get("id") or node_id)
                evidence_key = f"{conversation_id}:{message_id}:{content_sha256(text)}"
                if evidence_key in seen_messages:
                    stats["duplicate_messages"] += 1
                    continue
                seen_messages.add(evidence_key)
                self.ingest_text(
                    text=text,
                    source_type="chatgpt",
                    external_id=f"{conversation_id}:{message_id}",
                    authored_by="user",
                    created_at=str(message.get("create_time")) if message.get("create_time") else None,
                    attribution=Attribution.USER_DIRECT,
                )
                stats["user_messages"] += 1
                stats["tokens"] += len(tokenize(text))
        return dict(stats)

    def record_rejection(
        self,
        text: str,
        *,
        reason: str | None = None,
        created_at: str | None = None,
    ) -> None:
        normalized = " ".join(tokenize(text))
        if not normalized:
            raise ValueError("rejection text must contain at least one token")
        self.conn.execute(
            """
            INSERT INTO rejections(normalized_text, reason, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(normalized_text) DO UPDATE SET
                reason = excluded.reason,
                created_at = COALESCE(excluded.created_at, rejections.created_at)
            """,
            (normalized, reason, created_at),
        )
        self.conn.commit()

    def query(self, term: str) -> QueryResult:
        normalized_tokens = tokenize(term)
        if not normalized_tokens:
            raise ValueError("term must contain at least one token")
        normalized = " ".join(normalized_tokens)
        if len(normalized_tokens) == 1:
            table, column = "observations", "token"
        else:
            table, column = "phrases", "phrase"

        rows = self.conn.execute(
            f"SELECT id, attribution FROM {table} WHERE {column} = ? ORDER BY id",
            (normalized,),
        ).fetchall()
        counts: Counter[str] = Counter(row["attribution"] for row in rows)
        authored_total = counts[Attribution.USER_DIRECT.value] + counts[Attribution.META_REFERENCE.value]
        return QueryResult(
            term=normalized,
            authored_total=authored_total,
            ordinary_usage=counts[Attribution.USER_DIRECT.value],
            meta_reference=counts[Attribution.META_REFERENCE.value],
            quoted_usage=counts[Attribution.QUOTED.value],
            ai_generated=counts[Attribution.AI_GENERATED.value],
            ai_accepted=counts[Attribution.AI_ACCEPTED.value],
            ai_rejected=counts[Attribution.AI_REJECTED.value],
            evidence_ids=tuple(int(row["id"]) for row in rows),
        )

    def top_words(
        self,
        limit: int = 100,
        *,
        attribution: Attribution = Attribution.USER_DIRECT,
    ) -> list[tuple[str, int]]:
        rows = self.conn.execute(
            """
            SELECT token, COUNT(*) AS count
            FROM observations
            WHERE attribution = ?
            GROUP BY token
            ORDER BY count DESC, token ASC
            LIMIT ?
            """,
            (attribution.value, limit),
        ).fetchall()
        return [(str(row["token"]), int(row["count"])) for row in rows]

    def top_phrases(
        self,
        limit: int = 100,
        *,
        min_n: int = 2,
        max_n: int = 8,
        min_count: int = 2,
        attribution: Attribution = Attribution.USER_DIRECT,
    ) -> list[tuple[str, int, int]]:
        rows = self.conn.execute(
            """
            SELECT phrase, n, COUNT(*) AS count
            FROM phrases
            WHERE attribution = ? AND n BETWEEN ? AND ?
            GROUP BY phrase, n
            HAVING COUNT(*) >= ?
            ORDER BY count DESC, n DESC, phrase ASC
            LIMIT ?
            """,
            (attribution.value, min_n, max_n, min_count, limit),
        ).fetchall()
        return [(str(row["phrase"]), int(row["n"]), int(row["count"])) for row in rows]

    def corpus_digest(self) -> str:
        rows = self.conn.execute(
            """
            SELECT source_type, external_id, authored_by, created_at, content_sha256
            FROM sources ORDER BY id
            """
        ).fetchall()
        return canonical_sha256([dict(row) for row in rows])

    def _benchmark_policy(self, policy: EvolutionPolicy) -> float:
        policy.validate()
        source_count = int(self.conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0])
        token_count = int(self.conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0])
        unique_words = int(
            self.conn.execute("SELECT COUNT(DISTINCT token) FROM observations").fetchone()[0]
        )
        rejected = int(self.conn.execute("SELECT COUNT(*) FROM rejections").fetchone()[0])
        phrases = self.top_phrases(
            limit=500,
            min_n=policy.min_phrase_n,
            max_n=policy.max_phrase_n,
            min_count=policy.min_phrase_count,
        )
        phrase_signal = min(1.0, len(phrases) / 100.0)
        coverage = min(1.0, token_count / 1000.0)
        diversity = (
            0.0
            if token_count == 0
            else min(1.0, unique_words / max(1, token_count) * 10.0)
        )
        provenance = 1.0 if source_count > 0 and self.corpus_digest() else 0.0
        rejection_signal = min(1.0, rejected / 10.0) * (policy.rejection_penalty / 2.0)
        return round(
            0.30 * coverage
            + 0.20 * diversity
            + 0.20 * phrase_signal
            + 0.20 * provenance
            + 0.10 * rejection_signal,
            12,
        )

    @staticmethod
    def _phase(generation: int) -> str:
        phases = (
            "CORPUS_INTEGRITY",
            "TOKEN_MODEL",
            "PHRASE_DISCOVERY",
            "CONTEXT_CLASSIFICATION",
            "PERSONAL_VOCABULARY",
            "WRITING_STRUCTURE",
            "TEMPORAL_EVOLUTION",
            "DISTINCTIVENESS",
            "VOICE_RECONSTRUCTION",
            "ADVERSARIAL_VERIFICATION",
        )
        return phases[min(9, (generation - 1) // 10)]

    @staticmethod
    def _candidate_for(policy: EvolutionPolicy, generation: int) -> EvolutionPolicy:
        slot = (generation - 1) % 10
        phase = (generation - 1) // 10
        candidate = policy
        if phase == 2:
            if slot in {0, 3, 6}:
                candidate = replace(candidate, max_phrase_n=min(12, candidate.max_phrase_n + 1))
            elif slot in {1, 4, 7}:
                candidate = replace(
                    candidate,
                    min_phrase_count=max(1, candidate.min_phrase_count - 1),
                )
        elif phase == 3:
            candidate = replace(candidate, meta_penalty=min(2.0, candidate.meta_penalty + 0.05))
        elif phase == 4:
            candidate = replace(
                candidate,
                rejection_penalty=min(2.0, candidate.rejection_penalty + 0.05),
            )
        elif phase == 6:
            candidate = replace(candidate, recent_weight=min(2.0, candidate.recent_weight + 0.05))
        return candidate.validate()

    def evolve(
        self,
        generations: int = 100,
        *,
        initial_policy: EvolutionPolicy | None = None,
    ) -> EvolutionReport:
        if generations != 100:
            raise ValueError("Wordbook v0.1 evolution is fixed at exactly 100 bounded generations")
        current = (initial_policy or EvolutionPolicy()).validate()
        initial = current
        records: list[EvolutionGeneration] = []
        promoted = 0
        evidence_sha = self.corpus_digest()
        for generation in range(1, generations + 1):
            before = current
            candidate = self._candidate_for(before, generation)
            baseline_score = self._benchmark_policy(before)
            candidate_score = self._benchmark_policy(candidate)
            promote = candidate_score > baseline_score
            if promote:
                current = candidate
                promoted += 1
            records.append(
                EvolutionGeneration(
                    generation=generation,
                    phase=self._phase(generation),
                    baseline_score=baseline_score,
                    candidate_score=candidate_score,
                    promoted=promote,
                    policy_before_sha256=canonical_sha256(asdict(before)),
                    policy_after_sha256=canonical_sha256(asdict(current)),
                    evidence_sha256=evidence_sha,
                )
            )
        report = EvolutionReport(
            schema=SCHEMA_VERSION,
            generations=generations,
            promoted_generations=promoted,
            rejected_generations=generations - promoted,
            initial_policy=initial,
            final_policy=current,
            records=tuple(records),
        )
        rendered = report.to_dict()
        self.conn.execute(
            "INSERT INTO evolution_runs(report_sha256, report_json) VALUES (?, ?)",
            (
                canonical_sha256(rendered),
                json.dumps(rendered, sort_keys=True, ensure_ascii=False),
            ),
        )
        self.conn.commit()
        return report


def _json_default(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="centinal26-wordbook")
    parser.add_argument("--db", default="wordbook.sqlite3", help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest-chatgpt", help="ingest ChatGPT conversations.json")
    ingest.add_argument("path")

    query = sub.add_parser("query", help="query exact word or phrase counts")
    query.add_argument("term")

    words = sub.add_parser("top-words", help="show most frequent directly authored words")
    words.add_argument("--limit", type=int, default=100)

    phrases = sub.add_parser("top-phrases", help="show most frequent directly authored phrases")
    phrases.add_argument("--limit", type=int, default=100)
    phrases.add_argument("--min-count", type=int, default=2)

    reject = sub.add_parser("reject", help="record a user-rejected word or phrase")
    reject.add_argument("text")
    reject.add_argument("--reason")

    evolve = sub.add_parser(
        "evolve",
        help="run the fixed 100-generation bounded evolution campaign",
    )
    evolve.add_argument("--output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    with WordbookStore(args.db) as store:
        if args.command == "ingest-chatgpt":
            result: object = store.ingest_chatgpt_export(args.path)
        elif args.command == "query":
            result = store.query(args.term)
        elif args.command == "top-words":
            result = store.top_words(args.limit)
        elif args.command == "top-phrases":
            result = store.top_phrases(args.limit, min_count=args.min_count)
        elif args.command == "reject":
            store.record_rejection(args.text, reason=args.reason)
            result = {"status": "RECORDED", "text": args.text}
        elif args.command == "evolve":
            result = store.evolve().to_dict()
            if args.output:
                Path(args.output).write_text(
                    json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
        else:
            raise AssertionError(args.command)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, default=_json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
