from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from domain.publish import PublishJob, PublishTarget
from domain.station import Station, StationRole, StationStatus
from repository.database import create_engine, create_session_factory
from repository.models import Base
from repository.uow import SqlAlchemyUnitOfWorkFactory
from worker.composition import PublishTaskApplicationHandler, PublishTaskStateError
from worker.tasks import PublishTaskPayload


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    database_engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with database_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield database_engine
    await database_engine.dispose()


def make_station() -> Station:
    return Station(
        id=uuid4(),
        station_id=uuid4(),
        display_name="Client 01",
        hostname="client-01",
        role=StationRole.CLIENT,
        status=StationStatus.ONLINE,
    )


async def seed_job(
    factory: SqlAlchemyUnitOfWorkFactory,
) -> tuple[PublishJob, PublishTarget]:
    station = make_station()
    job = PublishJob(
        id=uuid4(),
        idempotency_key="worker-key",
        correlation_id=uuid4(),
        label="build-001",
        game_name="game",
    )
    target = PublishTarget(id=uuid4(), job_id=job.id, station_id=station.station_id)
    async with factory() as uow:
        await uow.stations.add(station)
        await uow.publish_jobs.add(job)
        await uow.publish_targets.add(target)
        await uow.commit()
    return job, target


class SpyExecutor:
    def __init__(self, calls: list[tuple[PublishJob, tuple[PublishTarget, ...], UUID]]) -> None:
        self._calls = calls

    async def execute(
        self,
        job: PublishJob,
        targets: tuple[PublishTarget, ...],
        *,
        correlation_id: UUID,
    ) -> None:
        self._calls.append((job, targets, correlation_id))


async def test_handler_reloads_job_and_targets_per_message(
    engine: AsyncEngine,
) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
    job, target = await seed_job(factory)
    calls: list[tuple[PublishJob, tuple[PublishTarget, ...], UUID]] = []
    executor_instances = 0

    def executor_factory() -> SpyExecutor:
        nonlocal executor_instances
        executor_instances += 1
        return SpyExecutor(calls)

    handler = PublishTaskApplicationHandler(factory, executor_factory)
    payload = PublishTaskPayload(job.id, job.correlation_id, job.idempotency_key)
    await handler.handle(payload)
    await handler.handle(payload)

    assert executor_instances == 2
    assert calls == [(job, (target,), job.correlation_id)] * 2


@pytest.mark.parametrize(
    ("idempotency_key", "payload_correlation_id", "message"),
    [
        ("wrong-key", None, "idempotency key"),
        ("worker-key", UUID(int=0), "correlation ID"),
    ],
)
async def test_handler_rejects_payload_that_does_not_match_durable_job(
    engine: AsyncEngine,
    idempotency_key: str,
    payload_correlation_id: UUID | None,
    message: str,
) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
    job, _ = await seed_job(factory)
    payload = PublishTaskPayload(
        job.id,
        job.correlation_id if payload_correlation_id is None else payload_correlation_id,
        idempotency_key,
    )

    with pytest.raises(PublishTaskStateError, match=message):
        await PublishTaskApplicationHandler(factory, lambda: SpyExecutor([])).handle(payload)


async def test_handler_rejects_unknown_job(engine: AsyncEngine) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
    payload = PublishTaskPayload(uuid4(), uuid4(), "missing-key")

    with pytest.raises(PublishTaskStateError, match="publish job not found"):
        await PublishTaskApplicationHandler(factory, lambda: SpyExecutor([])).handle(payload)
