from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from application.publish_executor import FakePublishTaskExecutor
from domain.publish import PublishJob, PublishJobStatus, PublishTarget, TargetStatus
from domain.station import Station, StationRole, StationStatus
from repository.database import create_engine, create_session_factory
from repository.models import Base
from repository.uow import SqlAlchemyUnitOfWorkFactory
from truenas_adapter.mock_client import FakePublishStorageAdapter


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


def make_station() -> Station:
    return Station(
        id=uuid4(),
        station_id=uuid4(),
        display_name="Client",
        hostname="client",
        role=StationRole.CLIENT,
        status=StationStatus.ONLINE,
    )


def make_job(
    *, dry_run: bool, status: PublishJobStatus = PublishJobStatus.PUBLISHING
) -> PublishJob:
    return PublishJob(
        id=uuid4(),
        idempotency_key=f"executor-{uuid4()}",
        correlation_id=uuid4(),
        label="build",
        source_dataset="game",
        dry_run=dry_run,
        status=status,
        client_confirmation=True,
    )


async def seed(
    factory: SqlAlchemyUnitOfWorkFactory,
    job: PublishJob,
    stations: tuple[Station, ...],
) -> tuple[PublishTarget, ...]:
    targets = tuple(
        PublishTarget(
            id=uuid4(),
            job_id=job.id,
            station_id=station.station_id,
            preflight_status="pass",
        )
        for station in stations
    )
    async with factory() as uow:
        for station in stations:
            await uow.stations.add(station)
        await uow.publish_jobs.add(job)
        await uow.publish_targets.add_many(targets)
        await uow.commit()
    return targets


async def read_state(
    factory: SqlAlchemyUnitOfWorkFactory,
    job_id,
) -> tuple[PublishJob, tuple[PublishTarget, ...]]:
    async with factory() as uow:
        job = await uow.publish_jobs.get(job_id)
        targets = await uow.publish_targets.list_for_job(job_id)
    assert job is not None
    return job, targets


async def test_fake_executor_persists_dry_run_without_fake_storage_mutation(
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    station = make_station()
    job = make_job(dry_run=True)
    targets = await seed(uow_factory, job, (station,))
    adapter = FakePublishStorageAdapter({station.station_id: "old:station"})

    await FakePublishTaskExecutor(uow_factory, lambda: adapter).execute(
        job,
        targets,
        correlation_id=job.correlation_id,
    )

    stored_job, stored_targets = await read_state(uow_factory, job.id)
    assert stored_job.status is PublishJobStatus.PUBLISHING
    assert stored_targets[0].switch_status == "simulated"
    assert stored_targets[0].verify_status == "simulated"
    assert stored_targets[0].old_mapping == {"ref": "old:station"}
    assert adapter.masters == {}
    assert adapter.clones == {}


async def test_fake_executor_persists_successful_apply(
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    station = make_station()
    job = make_job(dry_run=False)
    targets = await seed(uow_factory, job, (station,))
    adapter = FakePublishStorageAdapter()

    await FakePublishTaskExecutor(uow_factory, lambda: adapter).execute(
        job,
        targets,
        correlation_id=job.correlation_id,
    )

    stored_job, stored_targets = await read_state(uow_factory, job.id)
    assert stored_job.status is PublishJobStatus.COMPLETED
    assert stored_targets[0].switch_status == "switched"
    assert stored_targets[0].verify_status == "verified"
    assert stored_targets[0].progress_percent == 100


async def test_fake_executor_persists_partial_failure_per_target(
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    first, second = make_station(), make_station()
    job = make_job(dry_run=False)
    targets = await seed(uow_factory, job, (first, second))
    adapter = FakePublishStorageAdapter(
        {first.station_id: "old:first", second.station_id: "old:second"}
    )
    adapter.fail_clone_for.add(second.station_id)

    await FakePublishTaskExecutor(uow_factory, lambda: adapter).execute(
        job,
        targets,
        correlation_id=job.correlation_id,
    )

    stored_job, stored_targets = await read_state(uow_factory, job.id)
    targets_by_station = {target.station_id: target for target in stored_targets}
    assert stored_job.status is PublishJobStatus.PARTIAL_FAILURE
    assert targets_by_station[first.station_id].verify_status == "verified"
    assert targets_by_station[second.station_id].switch_status == TargetStatus.ERROR.value
    assert targets_by_station[second.station_id].error_code == "target_failed"
    assert adapter.mappings[second.station_id] == "old:second"


async def test_terminal_duplicate_delivery_does_not_create_fake_objects(
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    station = make_station()
    job = make_job(dry_run=False, status=PublishJobStatus.COMPLETED)
    targets = await seed(uow_factory, job, (station,))
    adapter = FakePublishStorageAdapter()

    await FakePublishTaskExecutor(uow_factory, lambda: adapter).execute(
        job,
        targets,
        correlation_id=job.correlation_id,
    )

    assert adapter.masters == {}
    assert adapter.clones == {}
