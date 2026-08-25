"""Publish job state machine and target results."""

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class PublishJobStatus(StrEnum):
    """Durable job states from draft through independent verification."""

    DRAFT = "draft"
    PREFLIGHT = "preflight"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    PUBLISHING = "publishing"
    SWITCHING = "switching"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"


class TargetStatus(StrEnum):
    """Outcome of one station target in a publish run."""

    SIMULATED = "simulated"
    VERIFIED = "verified"
    ERROR = "error"
    RECOVERY_REQUIRED = "recovery_required"


class StorageArtifactStatus(StrEnum):
    """Lifecycle of a dataset/clone created by a publish job."""

    CURRENT = "current"
    RETIRED = "retired"
    DELETED = "deleted"
    CLEANUP_FAILED = "cleanup_failed"


ALLOWED_TRANSITIONS: dict[PublishJobStatus, frozenset[PublishJobStatus]] = {
    PublishJobStatus.DRAFT: frozenset({PublishJobStatus.PREFLIGHT}),
    PublishJobStatus.PREFLIGHT: frozenset({PublishJobStatus.AWAITING_CONFIRMATION}),
    PublishJobStatus.AWAITING_CONFIRMATION: frozenset({PublishJobStatus.PUBLISHING}),
    PublishJobStatus.PUBLISHING: frozenset(
        {PublishJobStatus.SWITCHING, PublishJobStatus.COMPLETED, PublishJobStatus.FAILED}
    ),
    PublishJobStatus.SWITCHING: frozenset(
        {PublishJobStatus.VERIFYING, PublishJobStatus.PARTIAL_FAILURE, PublishJobStatus.FAILED}
    ),
    PublishJobStatus.VERIFYING: frozenset(
        {PublishJobStatus.COMPLETED, PublishJobStatus.PARTIAL_FAILURE, PublishJobStatus.FAILED}
    ),
    PublishJobStatus.COMPLETED: frozenset(),
    PublishJobStatus.PARTIAL_FAILURE: frozenset(),
    PublishJobStatus.FAILED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class PublishJob:
    """Immutable job state with explicit legal transitions."""

    id: UUID
    idempotency_key: str
    correlation_id: UUID
    label: str
    source_dataset: str
    dry_run: bool = False
    allow_hot_switch: bool = False
    status: PublishJobStatus = PublishJobStatus.DRAFT
    description: str | None = None
    status_reason: str | None = None
    operator_id: UUID | None = None
    client_confirmation: bool | None = None
    client_confirmation_at: datetime | None = None
    created_at: datetime | None = field(default=None, compare=False)
    started_at: datetime | None = field(default=None, compare=False)
    completed_at: datetime | None = field(default=None, compare=False)

    def transition(self, target: PublishJobStatus) -> "PublishJob":
        if target not in ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(f"illegal publish transition: {self.status} -> {target}")
        return replace(self, status=target)


@dataclass(frozen=True, slots=True)
class PublishJobHistory:
    """Read-only historical summary kept separate from workflow equality."""

    id: UUID
    label: str
    source_dataset: str
    status: PublishJobStatus
    status_reason: str | None
    dry_run: bool
    created_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class PublishTarget:
    """Materialized station selection and per-target publish state."""

    id: UUID
    job_id: UUID
    station_id: UUID
    selected: bool = True
    preflight_status: str | None = None
    preflight_result: dict[str, object] | None = None
    old_version_id: UUID | None = None
    new_version_id: UUID | None = None
    old_mapping: dict[str, object] | None = None
    new_mapping: dict[str, object] | None = None
    switch_status: str | None = None
    verify_status: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    progress_percent: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.progress_percent <= 100:
            raise ValueError("progress_percent must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class PublishTargetResult:
    """Safe result for one station; old mapping is retained in the result."""

    station_id: UUID
    status: TargetStatus
    old_mapping: str | None
    new_mapping: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    storage_created: bool = False


@dataclass(frozen=True, slots=True)
class PublishArtifact:
    """A TrueNAS dataset clone owned by one publish target."""

    id: UUID
    job_id: UUID
    station_id: UUID
    source_dataset: str
    dataset_name: str
    snapshot_ref: str
    mapping_ref: str
    created_at: datetime
    status: StorageArtifactStatus = StorageArtifactStatus.RETIRED
    is_current: bool = False
    deleted_at: datetime | None = None
    last_error: str | None = None
