from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Protocol

Json = dict[str, Any]


def _sha256(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class V0Operation(StrEnum):
    INIT_REPO = "v0.chat.init_repo"
    INIT_FILES = "v0.chat.init_files"
    CREATE = "v0.chat.create"
    SEND = "v0.chat.send"
    GET = "v0.chat.get"
    FIND = "v0.chat.find"
    PREPARE_PR = "v0.sync.prepare_pr"


READ_ONLY_OPERATIONS = {V0Operation.GET, V0Operation.FIND}


@dataclass(frozen=True)
class SoftwareRequest:
    operation: V0Operation
    arguments: Json
    request_id: str
    idempotency_key: str
    repository: str | None = None
    metadata: Json = field(default_factory=dict)

    @property
    def request_sha256(self) -> str:
        return _sha256(asdict(self))


@dataclass(frozen=True)
class SoftwareResult:
    request_sha256: str
    operation: V0Operation
    data: Json
    provider_receipt: Json
    response_sha256: str


@dataclass(frozen=True)
class PreparedPullRequest:
    repository: str
    base_branch: str
    head_branch: str
    title: str
    body: str
    changed_paths: tuple[str, ...]
    source_result_sha256: str
    synchronization_sha256: str
    github_write_authorized: bool = False


class SoftwareCreationProvider(Protocol):
    provider_id: str

    def invoke(self, operation: V0Operation, arguments: Json, idempotency_key: str) -> Json: ...


class FrostV0Adapter:
    """Provider-neutral Software/App Creation adapter.

    The adapter can call a configured v0-like provider, but it never creates a GitHub PR.
    `prepare_pr` emits deterministic synchronization metadata for a separately authorized
    GitHub capability. This preserves the execution/authorization boundary.
    """

    schema = "frost-call/1.0"

    def __init__(self, provider: SoftwareCreationProvider):
        self.provider = provider
        self._results_by_key: dict[str, SoftwareResult] = {}
        self._request_hash_by_key: dict[str, str] = {}

    def invoke(self, request: SoftwareRequest) -> SoftwareResult:
        if not request.request_id.strip() or not request.idempotency_key.strip():
            raise ValueError("request_id and idempotency_key are required")
        previous_hash = self._request_hash_by_key.get(request.idempotency_key)
        if previous_hash is not None:
            if previous_hash != request.request_sha256:
                raise ValueError("idempotency key reused for a different software request")
            return self._results_by_key[request.idempotency_key]

        data = self.provider.invoke(
            request.operation,
            request.arguments,
            request.idempotency_key,
        )
        receipt = {
            "provider_id": self.provider.provider_id,
            "operation": request.operation.value,
            "idempotency_key": request.idempotency_key,
        }
        result = SoftwareResult(
            request_sha256=request.request_sha256,
            operation=request.operation,
            data=data,
            provider_receipt=receipt,
            response_sha256=_sha256(data),
        )
        self._request_hash_by_key[request.idempotency_key] = request.request_sha256
        self._results_by_key[request.idempotency_key] = result
        return result

    @staticmethod
    def prepare_pr(
        *,
        repository: str,
        base_branch: str,
        head_branch: str,
        title: str,
        body: str,
        changed_paths: list[str],
        source_result: SoftwareResult,
    ) -> PreparedPullRequest:
        if not repository.strip() or not base_branch.strip() or not head_branch.strip():
            raise ValueError("repository, base_branch, and head_branch are required")
        if base_branch == head_branch:
            raise ValueError("base and head branches must differ")
        normalized = tuple(sorted(set(path.strip() for path in changed_paths if path.strip())))
        if not normalized:
            raise ValueError("changed_paths must not be empty")
        if any(path.startswith("/") or ".." in path.split("/") for path in normalized):
            raise ValueError("changed_paths must be repository-relative")
        sync_body = {
            "repository": repository,
            "base_branch": base_branch,
            "head_branch": head_branch,
            "title": title,
            "body": body,
            "changed_paths": normalized,
            "source_result_sha256": source_result.response_sha256,
            "github_write_authorized": False,
        }
        return PreparedPullRequest(
            repository=repository,
            base_branch=base_branch,
            head_branch=head_branch,
            title=title,
            body=body,
            changed_paths=normalized,
            source_result_sha256=source_result.response_sha256,
            synchronization_sha256=_sha256(sync_body),
            github_write_authorized=False,
        )
