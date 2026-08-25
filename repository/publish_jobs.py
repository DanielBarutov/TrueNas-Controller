"""SQLAlchemy repository for durable publish jobs."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from application.ports import PublishJobRepository
from domain.publish import PublishJob, PublishJobStatus
from domain.time import ensure_utc
from repository.models import PublishJobRecord, utc_now


class SqlAlchemyPublishJobRepository(PublishJobRepository):
    """Persist job state without embedding workflow decisions in SQL code."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, job_id: UUID) -> PublishJob | None:
        record = await self._session.get(PublishJobRecord, job_id)
        return None if record is None else self._to_domain(record)

    async def get_by_idempotency_key(self, idempotency_key: str) -> PublishJob | None:
        statement = select(PublishJobRecord).where(
            PublishJobRecord.idempotency_key == idempotency_key
        )
        record = await self._session.scalar(statement)
        return None if record is None else self._to_domain(record)

    async def add(self, job: PublishJob) -> None:
        self._session.add(
            PublishJobRecord(
                id=job.id,
                idempotency_key=job.idempotency_key,
                label=job.label,
                description=job.description,
                source_dataset=job.source_dataset,
                dry_run=job.dry_run,
                allow_hot_switch=job.allow_hot_switch,
                step=job.status.value,
                status=job.status,
                status_reason=job.status_reason,
                operator_id=job.operator_id,
                client_confirmation=job.client_confirmation,
                client_confirmation_at=job.client_confirmation_at,
                correlation_id=job.correlation_id,
            )
        )

    async def update(self, job: PublishJob) -> None:
        record = await self._session.get(PublishJobRecord, job.id, with_for_update=True)
        if record is None:
            raise ValueError("publish job not found")

        previous_status = record.status
        record.label = job.label
        record.description = job.description
        record.source_dataset = job.source_dataset
        record.dry_run = job.dry_run
        record.allow_hot_switch = job.allow_hot_switch
        record.step = job.status.value
        record.status = job.status
        record.status_reason = job.status_reason
        record.operator_id = job.operator_id
        record.client_confirmation = job.client_confirmation
        record.client_confirmation_at = job.client_confirmation_at
        if previous_status is not job.status:
            now = utc_now()
            if job.status is PublishJobStatus.PUBLISHING and record.started_at is None:
                record.started_at = now
            if job.status in {
                PublishJobStatus.COMPLETED,
                PublishJobStatus.PARTIAL_FAILURE,
                PublishJobStatus.FAILED,
            }:
                record.completed_at = now

    @staticmethod
    def _to_domain(record: PublishJobRecord) -> PublishJob:
        return PublishJob(
            id=record.id,
            idempotency_key=record.idempotency_key,
            correlation_id=record.correlation_id,
            label=record.label,
            source_dataset=record.source_dataset,
            dry_run=record.dry_run,
            allow_hot_switch=record.allow_hot_switch,
            status=PublishJobStatus(record.status),
            description=record.description,
            status_reason=record.status_reason,
            operator_id=record.operator_id,
            client_confirmation=record.client_confirmation,
            client_confirmation_at=(
                None
                if record.client_confirmation_at is None
                else ensure_utc(record.client_confirmation_at)
            ),
        )
