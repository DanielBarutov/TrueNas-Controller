"""SQLAlchemy repository for publish-created dataset clones."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from application.ports import PublishArtifactRepository
from domain.publish import PublishArtifact, StorageArtifactStatus
from domain.time import ensure_utc
from repository.models import PublishArtifactRecord


class SqlAlchemyPublishArtifactRepository(PublishArtifactRepository):
    """Persist artifacts without deciding when a remote dataset is safe to delete."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_job(self, job_id: UUID) -> tuple[PublishArtifact, ...]:
        statement = (
            select(PublishArtifactRecord)
            .where(PublishArtifactRecord.job_id == job_id)
            .order_by(PublishArtifactRecord.created_at, PublishArtifactRecord.station_id)
        )
        records = (await self._session.scalars(statement)).all()
        return tuple(self._to_domain(record) for record in records)

    async def save(self, artifact: PublishArtifact) -> None:
        statement = select(PublishArtifactRecord).where(
            PublishArtifactRecord.job_id == artifact.job_id,
            PublishArtifactRecord.station_id == artifact.station_id,
        )
        record = await self._session.scalar(statement)
        if record is None:
            self._session.add(self._to_record(artifact))
            return
        record.source_dataset = artifact.source_dataset
        record.dataset_name = artifact.dataset_name
        record.snapshot_ref = artifact.snapshot_ref
        record.mapping_ref = artifact.mapping_ref
        record.status = artifact.status
        record.is_current = artifact.is_current
        record.deleted_at = artifact.deleted_at
        record.last_error = artifact.last_error

    async def retire_station_artifacts(self, station_id: UUID, except_id: UUID) -> None:
        await self._session.execute(
            update(PublishArtifactRecord)
            .where(
                PublishArtifactRecord.station_id == station_id,
                PublishArtifactRecord.id != except_id,
                PublishArtifactRecord.is_current.is_(True),
            )
            .values(is_current=False, status=StorageArtifactStatus.RETIRED)
        )

    async def list_cleanup_candidates(
        self,
        *,
        before: datetime,
        limit: int,
    ) -> tuple[PublishArtifact, ...]:
        statement = (
            select(PublishArtifactRecord)
            .where(
                PublishArtifactRecord.is_current.is_(False),
                PublishArtifactRecord.status.in_(
                    (StorageArtifactStatus.RETIRED, StorageArtifactStatus.CLEANUP_FAILED)
                ),
                PublishArtifactRecord.dataset_name != PublishArtifactRecord.source_dataset,
                PublishArtifactRecord.created_at <= before,
            )
            .order_by(PublishArtifactRecord.created_at)
            .limit(limit)
        )
        records = (await self._session.scalars(statement)).all()
        return tuple(self._to_domain(record) for record in records)

    async def mark_deleted(self, artifact_id: UUID, deleted_at: datetime) -> None:
        record = await self._session.get(PublishArtifactRecord, artifact_id, with_for_update=True)
        if record is None:
            raise ValueError("publish artifact not found")
        record.status = StorageArtifactStatus.DELETED
        record.is_current = False
        record.deleted_at = deleted_at
        record.last_error = None

    async def mark_cleanup_failed(self, artifact_id: UUID, error: str) -> None:
        record = await self._session.get(PublishArtifactRecord, artifact_id, with_for_update=True)
        if record is None:
            raise ValueError("publish artifact not found")
        record.status = StorageArtifactStatus.CLEANUP_FAILED
        record.last_error = " ".join(error.split())[:1000]

    @staticmethod
    def _to_record(artifact: PublishArtifact) -> PublishArtifactRecord:
        return PublishArtifactRecord(
            id=artifact.id,
            job_id=artifact.job_id,
            station_id=artifact.station_id,
            source_dataset=artifact.source_dataset,
            dataset_name=artifact.dataset_name,
            snapshot_ref=artifact.snapshot_ref,
            mapping_ref=artifact.mapping_ref,
            created_at=artifact.created_at,
            status=artifact.status,
            is_current=artifact.is_current,
            deleted_at=artifact.deleted_at,
            last_error=artifact.last_error,
        )

    @staticmethod
    def _to_domain(record: PublishArtifactRecord) -> PublishArtifact:
        return PublishArtifact(
            id=record.id,
            job_id=record.job_id,
            station_id=record.station_id,
            source_dataset=record.source_dataset,
            dataset_name=record.dataset_name,
            snapshot_ref=record.snapshot_ref,
            mapping_ref=record.mapping_ref,
            created_at=ensure_utc(record.created_at),
            status=StorageArtifactStatus(record.status),
            is_current=record.is_current,
            deleted_at=None if record.deleted_at is None else ensure_utc(record.deleted_at),
            last_error=record.last_error,
        )
