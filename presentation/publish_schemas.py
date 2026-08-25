"""Pydantic schemas for the publish draft HTTP contract."""

from uuid import UUID

from pydantic import BaseModel, Field

from application.publish_commands import PublishJobDraft
from application.publish_confirmation import PublishPreflightResult
from application.publish_queries import PublishJobView
from domain.preflight import PreflightReport
from domain.publish import PublishJobStatus
from presentation.preflight_schemas import CheckResponse, PreflightResponse


class PublishJobCreateRequest(BaseModel):
    """Operator input for one durable draft and its station selection."""

    label: str = Field(min_length=1, max_length=255)
    source_dataset: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    station_ids: list[UUID] = Field(min_length=1)
    idempotency_key: str = Field(min_length=1, max_length=200)
    correlation_id: UUID | None = None
    dry_run: bool = True
    allow_hot_switch: bool = False


class PublishPrepareRequest(BaseModel):
    """Operator input for the server-side preflight and confirmation gate."""

    admin_station_id: UUID | None = None
    confirmation: bool | None = None


class PublishJobDraftResponse(BaseModel):
    """Safe draft summary without mappings, credentials or storage details."""

    id: UUID
    idempotency_key: str
    correlation_id: UUID
    label: str
    source_dataset: str
    status: PublishJobStatus
    dry_run: bool
    allow_hot_switch: bool
    station_ids: list[UUID]

    @classmethod
    def from_draft(cls, draft: PublishJobDraft) -> "PublishJobDraftResponse":
        return cls(
            id=draft.job.id,
            idempotency_key=draft.job.idempotency_key,
            correlation_id=draft.job.correlation_id,
            label=draft.job.label,
            source_dataset=draft.job.source_dataset,
            status=draft.job.status,
            dry_run=draft.job.dry_run,
            allow_hot_switch=draft.job.allow_hot_switch,
            station_ids=[target.station_id for target in draft.targets],
        )


class PublishGateResponse(BaseModel):
    """Explainable, secret-free wizard gate result."""

    status: str
    can_advance: bool
    selected_station_ids: list[UUID]
    reasons: list[str]


class PublishPrepareResponse(BaseModel):
    """Fresh reports and persisted job state returned by prepare."""

    job_id: UUID
    status: PublishJobStatus
    client_confirmation: bool | None
    gate: PublishGateResponse
    admin_report: PreflightResponse | None
    client_reports: list[PreflightResponse]

    @classmethod
    def from_result(cls, result: PublishPreflightResult) -> "PublishPrepareResponse":
        return cls(
            job_id=result.job.id,
            status=result.job.status,
            client_confirmation=result.job.client_confirmation,
            gate=PublishGateResponse(
                status=result.gate.status,
                can_advance=result.gate.can_advance,
                selected_station_ids=list(result.gate.selected_station_ids),
                reasons=list(result.gate.reasons),
            ),
            admin_report=(
                None
                if result.admin_report is None
                else _preflight_response(result.admin_report)
            ),
            client_reports=[
                _preflight_response(report) for report in result.client_reports.values()
            ],
        )


class PublishDispatchResponse(BaseModel):
    """Safe acknowledgement that the job entered the outbox-backed queue path."""

    job_id: UUID
    status: PublishJobStatus
    accepted: bool = True


def _preflight_response(report: PreflightReport) -> PreflightResponse:
    return PreflightResponse(
        station_id=report.station_id,
        status=report.status,
        can_publish=report.can_publish,
        evaluated_at=report.evaluated_at,
        checks=[
            CheckResponse(
                status=check.status,
                code=check.code,
                message=check.message,
                observed_at=check.observed_at,
                source_snapshot_id=check.source_snapshot_id,
            )
            for check in report.checks
        ],
    )


class PublishTargetStatusResponse(BaseModel):
    """Safe per-station outcome without raw storage mapping details."""

    station_id: UUID
    selected: bool
    preflight_status: str | None
    switch_status: str | None
    verify_status: str | None
    error_code: str | None
    error_message: str | None
    progress_percent: int


class PublishJobResponse(BaseModel):
    """Read model used to restore the operator's publish wizard."""

    id: UUID
    idempotency_key: str
    correlation_id: UUID
    label: str
    source_dataset: str
    description: str | None
    status: PublishJobStatus
    dry_run: bool
    allow_hot_switch: bool
    targets: list[PublishTargetStatusResponse]

    @classmethod
    def from_view(cls, view: PublishJobView) -> "PublishJobResponse":
        return cls(
            id=view.job.id,
            idempotency_key=view.job.idempotency_key,
            correlation_id=view.job.correlation_id,
            label=view.job.label,
            source_dataset=view.job.source_dataset,
            description=view.job.description,
            status=view.job.status,
            dry_run=view.job.dry_run,
            allow_hot_switch=view.job.allow_hot_switch,
            targets=[
                PublishTargetStatusResponse(
                    station_id=target.station_id,
                    selected=target.selected,
                    preflight_status=target.preflight_status,
                    switch_status=target.switch_status,
                    verify_status=target.verify_status,
                    error_code=target.error_code,
                    error_message=target.error_message,
                    progress_percent=target.progress_percent,
                )
                for target in view.targets
            ],
        )
