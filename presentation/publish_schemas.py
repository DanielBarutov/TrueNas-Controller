"""Pydantic schemas for the publish draft HTTP contract."""

from uuid import UUID

from pydantic import BaseModel, Field

from application.publish_commands import PublishJobDraft
from application.publish_queries import PublishJobView
from domain.publish import PublishJobStatus


class PublishJobCreateRequest(BaseModel):
    """Operator input for one durable draft and its station selection."""

    label: str = Field(min_length=1, max_length=255)
    game_name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    station_ids: list[UUID] = Field(min_length=1)
    idempotency_key: str = Field(min_length=1, max_length=200)
    correlation_id: UUID | None = None
    dry_run: bool = True
    allow_hot_switch: bool = False


class PublishJobDraftResponse(BaseModel):
    """Safe draft summary without mappings, credentials or storage details."""

    id: UUID
    idempotency_key: str
    correlation_id: UUID
    label: str
    game_name: str
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
            game_name=draft.job.game_name,
            status=draft.job.status,
            dry_run=draft.job.dry_run,
            allow_hot_switch=draft.job.allow_hot_switch,
            station_ids=[target.station_id for target in draft.targets],
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
    game_name: str
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
            game_name=view.job.game_name,
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
