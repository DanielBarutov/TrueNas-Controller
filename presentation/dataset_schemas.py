"""Public schemas for the tracked TrueNAS dataset inventory."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from domain.publish import PublishArtifact


class DatasetResponse(BaseModel):
    """Safe metadata displayed in the operator dataset table."""

    id: UUID
    job_id: UUID
    station_id: UUID
    source_dataset: str
    dataset_name: str
    snapshot_ref: str
    mapping_ref: str
    status: str
    is_current: bool
    created_at: datetime
    deleted_at: datetime | None
    last_error: str | None

    @classmethod
    def from_domain(cls, artifact: PublishArtifact) -> "DatasetResponse":
        return cls(
            id=artifact.id,
            job_id=artifact.job_id,
            station_id=artifact.station_id,
            source_dataset=artifact.source_dataset,
            dataset_name=artifact.dataset_name,
            snapshot_ref=artifact.snapshot_ref,
            mapping_ref=artifact.mapping_ref,
            status=artifact.status.value,
            is_current=artifact.is_current,
            created_at=artifact.created_at,
            deleted_at=artifact.deleted_at,
            last_error=artifact.last_error,
        )


class DatasetDeleteRequest(BaseModel):
    """Selected inventory IDs sent from the checkbox table."""

    artifact_ids: list[UUID] = Field(min_length=1, max_length=100)


class DatasetDeleteResponse(BaseModel):
    """Acknowledgement that selected IDs entered the cleanup worker queue."""

    status: str = "accepted"
    artifact_ids: list[UUID]
