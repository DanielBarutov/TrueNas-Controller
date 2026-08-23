from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from application.publish_dispatch import DispatchPublishJobUseCase
from domain.outbox import OutboxEvent
from domain.publish import PublishJob, PublishJobStatus, PublishTarget
from domain.station import Station, StationRole, StationStatus
from repository.database import create_engine, create_session_factory
from repository.models import Base
from repository.uow import SqlAlchemyUnitOfWorkFactory

NOW = datetime(2026, 8, 23, 12, tzinfo=UTC)


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    database_engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with database_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield database_engine
    await database_engine.dispose()


@pytest.fixture
def uow_factory(engine: AsyncEngine) -> SqlAlchemyUnitOfWorkFactory:
    return SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))


def make_job_and_target() -> tuple[Station, PublishJob, PublishTarget]:
    station = Station(
        id=uuid4(),
        station_id=uuid4(),
        display_name="Client 01",
        hostname="client-01",
        role=StationRole.CLIENT,
        status=StationStatus.ONLINE,
    )
    job = PublishJob(
        id=uuid4(),
        idempotency_key="outbox-job",
        correlation_id=uuid4(),
        label="build",
        game_name="game",
        status=PublishJobStatus.AWAITING_CONFIRMATION,
        client_confirmation=True,
    )
    target = PublishTarget(
        id=uuid4(),
        job_id=job.id,
        station_id=station.station_id,
        preflight_status="pass",
    )
    return station, job, target


def make_event(job: PublishJob) -> OutboxEvent:
    return OutboxEvent(
        id=uuid4(),
        aggregate_id=job.id,
        event_type="publish.dispatch",
        payload={
            "job_id": str(job.id),
            "correlation_id": str(job.correlation_id),
            "idempotency_key": job.idempotency_key,
        },
        correlation_id=job.correlation_id,
        available_at=NOW,
    )


async def test_dispatch_persists_job_and_outbox_event_together(
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    station, job, target = make_job_and_target()
    async with uow_factory() as uow:
        await uow.stations.add(station)
        await uow.publish_jobs.add(job)
        await uow.publish_targets.add(target)
        await uow.commit()

    result = await DispatchPublishJobUseCase(uow_factory).execute(job_id=job.id)

    assert result.job.status is PublishJobStatus.PUBLISHING
    async with uow_factory() as uow:
        stored_job = await uow.publish_jobs.get(job.id)
        events = await uow.outbox_events.claim_pending(
            limit=1,
            worker_id="test-relay",
            now=datetime.now(UTC),
            lease_for=timedelta(minutes=1),
        )
        await uow.commit()
    assert stored_job is not None and stored_job.status is PublishJobStatus.PUBLISHING
    assert len(events) == 1
    assert events[0].payload["job_id"] == str(job.id)


async def test_outbox_lease_excludes_claimed_event_until_released(
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    _, job, _ = make_job_and_target()
    event = make_event(job)
    async with uow_factory() as uow:
        await uow.publish_jobs.add(job)
        await uow.outbox_events.add(event)
        await uow.commit()

    async with uow_factory() as uow:
        claimed = await uow.outbox_events.claim_pending(
            limit=1,
            worker_id="test-relay",
            now=NOW + timedelta(seconds=1),
            lease_for=timedelta(minutes=1),
        )
        await uow.commit()
    async with uow_factory() as uow:
        second_claim = await uow.outbox_events.claim_pending(
            limit=1,
            worker_id="other-relay",
            now=NOW + timedelta(seconds=1),
            lease_for=timedelta(minutes=1),
        )
    async with uow_factory() as uow:
        expired_claim = await uow.outbox_events.claim_pending(
            limit=1,
            worker_id="recovery-relay",
            now=NOW + timedelta(minutes=2),
            lease_for=timedelta(minutes=1),
        )

    assert claimed[0].id == event.id
    assert second_claim == ()
    assert expired_claim[0].id == event.id


async def test_outbox_failure_retries_then_becomes_terminal(
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    _, job, _ = make_job_and_target()
    event = make_event(job)
    async with uow_factory() as uow:
        await uow.publish_jobs.add(job)
        await uow.outbox_events.add(event)
        await uow.commit()

    retry_at = NOW + timedelta(seconds=2)
    async with uow_factory() as uow:
        await uow.outbox_events.mark_failed(
            event.id,
            error="delivery failed",
            retry_at=retry_at,
            max_attempts=2,
        )
        await uow.commit()
    async with uow_factory() as uow:
        first = await uow.outbox_events.claim_pending(
            limit=1,
            worker_id="test-relay",
            now=retry_at,
            lease_for=timedelta(minutes=1),
        )
        await uow.commit()
    async with uow_factory() as uow:
        await uow.outbox_events.mark_failed(
            event.id,
            error="delivery failed again",
            retry_at=retry_at + timedelta(seconds=2),
            max_attempts=2,
        )
        await uow.commit()
        second = await uow.outbox_events.claim_pending(
            limit=1,
            worker_id="test-relay",
            now=retry_at + timedelta(seconds=2),
            lease_for=timedelta(minutes=1),
        )

    assert first[0].attempts == 1
    assert second == ()
    async with uow_factory() as uow:
        failed = await uow.outbox_events.claim_pending(
            limit=1,
            worker_id="test-relay",
            now=retry_at + timedelta(seconds=3),
            lease_for=timedelta(minutes=1),
        )
    assert failed == ()
