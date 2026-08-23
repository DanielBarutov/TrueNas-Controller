"""SQLAlchemy transactional outbox repository."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from application.ports import OutboxRepository
from domain.outbox import OutboxEvent, OutboxEventStatus
from domain.time import ensure_utc
from repository.models import OutboxEventRecord, utc_now


class SqlAlchemyOutboxRepository(OutboxRepository):
    """Lease and update outbox rows in short database transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: OutboxEvent) -> None:
        self._session.add(
            OutboxEventRecord(
                id=event.id,
                aggregate_id=event.aggregate_id,
                event_type=event.event_type,
                payload=event.payload,
                correlation_id=event.correlation_id,
                status=event.status,
                attempts=event.attempts,
                available_at=event.available_at or utc_now(),
                created_at=event.created_at or utc_now(),
            )
        )

    async def claim_pending(
        self,
        *,
        limit: int,
        worker_id: str,
        now: datetime,
        lease_for: timedelta,
    ) -> tuple[OutboxEvent, ...]:
        if limit < 1:
            return ()
        statement = (
            select(OutboxEventRecord)
            .where(
                OutboxEventRecord.status == OutboxEventStatus.PENDING,
                OutboxEventRecord.available_at <= now,
                or_(
                    OutboxEventRecord.locked_at.is_(None),
                    OutboxEventRecord.lease_expires_at <= now,
                ),
            )
            .order_by(OutboxEventRecord.created_at, OutboxEventRecord.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        records = (await self._session.scalars(statement)).all()
        for record in records:
            record.locked_at = now
            record.locked_by = worker_id
            record.lease_expires_at = now + lease_for
        return tuple(self._to_domain(record) for record in records)

    async def mark_dispatched(self, event_id: UUID, dispatched_at: datetime) -> None:
        record = await self._session.get(OutboxEventRecord, event_id, with_for_update=True)
        if record is None:
            raise ValueError("outbox event not found")
        record.status = OutboxEventStatus.DISPATCHED
        record.dispatched_at = dispatched_at
        record.locked_at = None
        record.locked_by = None
        record.lease_expires_at = None

    async def mark_failed(
        self,
        event_id: UUID,
        *,
        error: str,
        retry_at: datetime,
        max_attempts: int,
    ) -> None:
        record = await self._session.get(OutboxEventRecord, event_id, with_for_update=True)
        if record is None:
            raise ValueError("outbox event not found")
        record.attempts += 1
        record.status = (
            OutboxEventStatus.FAILED
            if record.attempts >= max_attempts
            else OutboxEventStatus.PENDING
        )
        record.available_at = retry_at
        record.last_error = error[:1000]
        record.locked_at = None
        record.locked_by = None
        record.lease_expires_at = None

    @staticmethod
    def _to_domain(record: OutboxEventRecord) -> OutboxEvent:
        return OutboxEvent(
            id=record.id,
            aggregate_id=record.aggregate_id,
            event_type=record.event_type,
            payload=record.payload,
            correlation_id=record.correlation_id,
            status=OutboxEventStatus(record.status),
            attempts=record.attempts,
            available_at=ensure_utc(record.available_at),
            created_at=ensure_utc(record.created_at),
        )
