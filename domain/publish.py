"""Publish job state machine and target results."""

from dataclasses import dataclass, replace
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


ALLOWED_TRANSITIONS: dict[PublishJobStatus, frozenset[PublishJobStatus]] = {
    PublishJobStatus.DRAFT: frozenset({PublishJobStatus.PREFLIGHT}),
    PublishJobStatus.PREFLIGHT: frozenset({PublishJobStatus.AWAITING_CONFIRMATION}),
    PublishJobStatus.AWAITING_CONFIRMATION: frozenset({PublishJobStatus.PUBLISHING}),
    PublishJobStatus.PUBLISHING: frozenset({PublishJobStatus.SWITCHING, PublishJobStatus.FAILED}),
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
    game_name: str
    dry_run: bool = True
    allow_hot_switch: bool = False
    status: PublishJobStatus = PublishJobStatus.DRAFT

    def transition(self, target: PublishJobStatus) -> "PublishJob":
        if target not in ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(f"illegal publish transition: {self.status} -> {target}")
        return replace(self, status=target)


@dataclass(frozen=True, slots=True)
class PublishTargetResult:
    """Safe result for one station; old mapping is retained in the result."""

    station_id: UUID
    status: TargetStatus
    old_mapping: str | None
    new_mapping: str | None = None
    error_code: str | None = None
    error_message: str | None = None
