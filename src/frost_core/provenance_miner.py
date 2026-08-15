from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import BinaryIO


class EvidenceStrength(StrEnum):
    NOT_FOUND = "NOT_FOUND"
    WEAK_LEAD = "WEAK_LEAD"
    FOUND_CANDIDATE = "FOUND_CANDIDATE"
    HASH_MATCH = "HASH_MATCH"


@dataclass(frozen=True)
class ArtifactFinding:
    source: str
    member: str | None
    sha256: str
    size: int
    strength: EvidenceStrength
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class MinerReport:
    findings: tuple[ArtifactFinding, ...]
    searched_files: int
    searched_archives: int
    skipped_unsafe_members: int
    truncated: bool
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "findings": [asdict(finding) for finding in self.findings],
            "searched_files": self.searched_files,
            "searched_archives": self.searched_archives,
            "skipped_unsafe_members": self.skipped_unsafe_members,
            "truncated": self.truncated,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class MinerQuery:
    expected_sha256: tuple[str, ...] = ()
    filename_terms: tuple[str, ...] = ()
    text_terms: tuple[str, ...] = ()


@dataclass
class _Counters:
    files: int = 0
    archives: int = 0
    skipped: int = 0
    bytes_read: int = 0
    truncated: bool = False
    warnings: list[str] = field(default_factory=list)


class ReadOnlyProvenanceMiner:
    """Bounded, read-only source and archive archaeology.

    Archive members are inspected in memory. Nothing discovered is executed, sourced, or
    written to an extraction path. Nested ZIP traversal is bounded by depth, member count,
    individual-member size, and total bytes read.
    """

    def __init__(
        self,
        *,
        max_depth: int = 3,
        max_members: int = 10_000,
        max_member_bytes: int = 16 * 1024 * 1024,
        max_total_bytes: int = 256 * 1024 * 1024,
    ):
        if min(max_depth, max_members, max_member_bytes, max_total_bytes) < 1:
            raise ValueError("all miner bounds must be positive")
        self.max_depth = max_depth
        self.max_members = max_members
        self.max_member_bytes = max_member_bytes
        self.max_total_bytes = max_total_bytes

    def scan(self, roots: list[Path], query: MinerQuery) -> MinerReport:
        counters = _Counters()
        findings: list[ArtifactFinding] = []
        for root in roots:
            if counters.truncated:
                break
            if root.is_file():
                self._scan_path(root, query, findings, counters)
            elif root.is_dir():
                for path in sorted(item for item in root.rglob("*") if item.is_file()):
                    if counters.truncated:
                        break
                    self._scan_path(path, query, findings, counters)
            else:
                counters.warnings.append(f"unreadable_or_missing:{root}")
        findings.sort(
            key=lambda finding: (self._strength_rank(finding.strength), finding.source),
            reverse=True,
        )
        return MinerReport(
            findings=tuple(findings),
            searched_files=counters.files,
            searched_archives=counters.archives,
            skipped_unsafe_members=counters.skipped,
            truncated=counters.truncated,
            warnings=tuple(counters.warnings),
        )

    def _scan_path(
        self,
        path: Path,
        query: MinerQuery,
        findings: list[ArtifactFinding],
        counters: _Counters,
    ) -> None:
        try:
            size = path.stat().st_size
        except OSError as error:
            counters.warnings.append(f"stat_failed:{path}:{type(error).__name__}")
            return
        if size > self.max_member_bytes:
            counters.warnings.append(f"oversize_file_skipped:{path}:{size}")
            return
        try:
            data = path.read_bytes()
        except OSError as error:
            counters.warnings.append(f"read_failed:{path}:{type(error).__name__}")
            return
        if not self._consume(len(data), counters):
            return
        counters.files += 1
        finding = self._classify(str(path), None, data, query)
        if finding is not None:
            findings.append(finding)
        if self._looks_like_zip(path.name, data):
            self._scan_zip_bytes(str(path), data, 1, query, findings, counters)

    def _scan_zip_bytes(
        self,
        source: str,
        data: bytes,
        depth: int,
        query: MinerQuery,
        findings: list[ArtifactFinding],
        counters: _Counters,
    ) -> None:
        if depth > self.max_depth or counters.truncated:
            return
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
        except (zipfile.BadZipFile, OSError):
            counters.warnings.append(f"invalid_zip:{source}")
            return
        counters.archives += 1
        with archive:
            infos = archive.infolist()
            if len(infos) > self.max_members:
                counters.warnings.append(f"archive_member_limit:{source}:{len(infos)}")
                infos = infos[: self.max_members]
                counters.truncated = True
            for info in infos:
                if counters.truncated and counters.bytes_read >= self.max_total_bytes:
                    break
                if info.is_dir():
                    continue
                if not self._safe_member_name(info.filename):
                    counters.skipped += 1
                    continue
                if info.file_size > self.max_member_bytes:
                    counters.warnings.append(
                        f"oversize_member_skipped:{source}!{info.filename}:{info.file_size}"
                    )
                    continue
                try:
                    with archive.open(info, "r") as stream:
                        member = self._read_bounded(stream, info.file_size)
                except (RuntimeError, OSError, zipfile.BadZipFile) as error:
                    counters.warnings.append(
                        f"member_read_failed:{source}!{info.filename}:{type(error).__name__}"
                    )
                    continue
                if not self._consume(len(member), counters):
                    break
                counters.files += 1
                finding = self._classify(source, info.filename, member, query)
                if finding is not None:
                    findings.append(finding)
                if self._looks_like_zip(info.filename, member):
                    nested_source = f"{source}!{info.filename}"
                    self._scan_zip_bytes(
                        nested_source,
                        member,
                        depth + 1,
                        query,
                        findings,
                        counters,
                    )

    def _read_bounded(self, stream: BinaryIO, declared_size: int) -> bytes:
        if declared_size > self.max_member_bytes:
            raise ValueError("member exceeds configured byte bound")
        data = stream.read(self.max_member_bytes + 1)
        if len(data) > self.max_member_bytes:
            raise ValueError("member expanded beyond configured byte bound")
        return data

    def _classify(
        self,
        source: str,
        member: str | None,
        data: bytes,
        query: MinerQuery,
    ) -> ArtifactFinding | None:
        digest = hashlib.sha256(data).hexdigest()
        reasons: list[str] = []
        strength = EvidenceStrength.NOT_FOUND
        expected = {item.lower() for item in query.expected_sha256}
        if digest.lower() in expected:
            strength = EvidenceStrength.HASH_MATCH
            reasons.append("exact_sha256")
        name = (member or source).lower()
        for term in query.filename_terms:
            if term.lower() in name:
                reasons.append(f"filename:{term}")
                if strength == EvidenceStrength.NOT_FOUND:
                    strength = EvidenceStrength.FOUND_CANDIDATE
        if query.text_terms and self._probably_text(data):
            text = data.decode("utf-8", errors="ignore").lower()
            matched = [term for term in query.text_terms if term.lower() in text]
            if matched:
                reasons.extend(f"text:{term}" for term in matched)
                if strength == EvidenceStrength.NOT_FOUND:
                    strength = EvidenceStrength.WEAK_LEAD
        if not reasons:
            return None
        return ArtifactFinding(
            source=source,
            member=member,
            sha256=digest,
            size=len(data),
            strength=strength,
            reasons=tuple(reasons),
        )

    def _consume(self, amount: int, counters: _Counters) -> bool:
        if counters.bytes_read + amount > self.max_total_bytes:
            counters.truncated = True
            counters.warnings.append("max_total_bytes_reached")
            return False
        counters.bytes_read += amount
        return True

    @staticmethod
    def _looks_like_zip(name: str, data: bytes) -> bool:
        return name.lower().endswith(".zip") or data[:4] in {b"PK\x03\x04", b"PK\x05\x06"}

    @staticmethod
    def _safe_member_name(name: str) -> bool:
        pure = PurePosixPath(name)
        if pure.is_absolute() or ".." in pure.parts:
            return False
        return not bool(re.match(r"^[A-Za-z]:", name))

    @staticmethod
    def _probably_text(data: bytes) -> bool:
        return b"\x00" not in data[:4096]

    @staticmethod
    def _strength_rank(strength: EvidenceStrength) -> int:
        return {
            EvidenceStrength.NOT_FOUND: 0,
            EvidenceStrength.WEAK_LEAD: 1,
            EvidenceStrength.FOUND_CANDIDATE: 2,
            EvidenceStrength.HASH_MATCH: 3,
        }[strength]
