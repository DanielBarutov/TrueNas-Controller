from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from domain.publish import (
    PublishArtifact,
    PublishJob,
    PublishJobStatus,
    PublishTarget,
    StorageArtifactStatus,
)
from domain.station import Station, StationRole, StationStatus
from repository.database import create_engine, create_session_factory
from repository.models import Base
from repository.uow import SqlAlchemyUnitOfWorkFactory


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


def make_job(*, idempotency_key: str = "job-key") -> PublishJob:
    return PublishJob(
        id=uuid4(),
        idempotency_key=idempotency_key,
        correlation_id=uuid4(),
        label="build-001",
        source_dataset="game",
        description="nightly build",
        client_confirmation=True,
    )


def make_target(job: PublishJob, station: Station) -> PublishTarget:
    return PublishTarget(
        id=uuid4(),
        job_id=job.id,
        station_id=station.station_id,
        preflight_status="passed",
        preflight_result={"can_publish": True},
        old_mapping={"dataset": "old"},
    )


@pytest.fixture
def uow_factory(engine: AsyncEngine) -> SqlAlchemyUnitOfWorkFactory:
    return SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))


async def test_publish_job_and_targets_round_trip_with_stable_station_id(
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    station = make_station()
    job = make_job()
    target = make_target(job, station)

    async with uow_factory() as uow:
        await uow.stations.add(station)
        await uow.publish_jobs.add(job)
        await uow.publish_targets.add_many((target,))
        await uow.commit()

    async with uow_factory() as uow:
        assert await uow.publish_jobs.get(job.id) == job
        assert await uow.publish_jobs.get_by_idempotency_key(job.idempotency_key) == job
        assert await uow.publish_targets.list_for_job(job.id) == (target,)

        updated = job.transition(PublishJobStatus.PREFLIGHT)
        await uow.publish_jobs.update(updated)
        await uow.commit()

    async with uow_factory() as uow:
        assert await uow.publish_jobs.get(job.id) == updated


async def test_publish_job_and_targets_commit_as_one_transaction(
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    station = make_station()
    job = make_job()
    target = make_target(job, station)

    with pytest.raises(RuntimeError, match="abort publish draft"):
        async with uow_factory() as uow:
            await uow.stations.add(station)
            await uow.publish_jobs.add(job)
            await uow.publish_targets.add(target)
            raise RuntimeError("abort publish draft")

    async with uow_factory() as uow:
        assert await uow.publish_jobs.get(job.id) is None


async def test_publish_job_idempotency_key_is_unique(
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    first = make_job()
    duplicate = make_job()

    async with uow_factory() as uow:
        await uow.publish_jobs.add(first)
        await uow.commit()

    with pytest.raises(IntegrityError):
        async with uow_factory() as uow:
            await uow.publish_jobs.add(duplicate)
            await uow.commit()


async def test_publish_target_station_is_unique_per_job(
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    station = make_station()
    job = make_job()
    first = make_target(job, station)
    duplicate = make_target(job, station)

    async with uow_factory() as uow:
        await uow.stations.add(station)
        await uow.publish_jobs.add(job)
        await uow.publish_targets.add(first)
        await uow.commit()

    with pytest.raises(IntegrityError):
        async with uow_factory() as uow:
            await uow.publish_targets.add(duplicate)
            await uow.commit()


async def test_publish_job_and_target_updates_round_trip(
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    station = make_station()
    job = make_job()
    target = make_target(job, station)
    confirmation_at = datetime(2026, 8, 23, 12, tzinfo=UTC)

    async with uow_factory() as uow:
        await uow.stations.add(station)
        await uow.publish_jobs.add(job)
        await uow.publish_targets.add(target)
        await uow.commit()

    updated_job = replace(
        job.transition(PublishJobStatus.PREFLIGHT),
        client_confirmation=True,
        client_confirmation_at=confirmation_at,
    )
    updated_target = replace(
        target,
        preflight_status="pass",
        preflight_result={"status": "pass"},
        progress_percent=25,
    )
    async with uow_factory() as uow:
        await uow.publish_jobs.update(updated_job)
        await uow.publish_targets.update(updated_target)
        await uow.commit()

    async with uow_factory() as uow:
        assert await uow.publish_jobs.get(job.id) == updated_job
        assert await uow.publish_targets.list_for_job(job.id) == (updated_target,)


async def test_publish_artifact_inventory_filters_deleted_and_loads_selected_ids(
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    station = make_station()
    deleted_station = replace(
        station,
        id=uuid4(),
        station_id=uuid4(),
        display_name="Client 02",
        hostname="client-02",
    )
    job = make_job(idempotency_key="artifact-inventory")
    created_at = datetime(2026, 9, 5, 11, tzinfo=UTC)
    active = PublishArtifact(
        id=uuid4(),
        job_id=job.id,
        station_id=station.station_id,
        source_dataset="games/master-games",
        dataset_name="games/clone-pc1",
        snapshot_ref="games/master-games@snapshot",
        mapping_ref="zvol/games/clone-pc1",
        created_at=created_at,
        status=StorageArtifactStatus.RETIRED,
    )
    deleted = PublishArtifact(
        id=uuid4(),
        job_id=job.id,
        station_id=deleted_station.station_id,
        source_dataset="games/master-games",
        dataset_name="games/clone-pc2",
        snapshot_ref="games/master-games@snapshot-2",
        mapping_ref="zvol/games/clone-pc2",
        created_at=datetime(2026, 9, 5, 10, tzinfo=UTC),
        status=StorageArtifactStatus.DELETED,
        deleted_at=datetime(2026, 9, 5, 12, tzinfo=UTC),
    )
    second_target = make_target(job, deleted_station)

    async with uow_factory() as uow:
        await uow.stations.add(station)
        await uow.stations.add(deleted_station)
        await uow.publish_jobs.add(job)
        await uow.publish_targets.add_many((make_target(job, station), second_target))
        await uow.publish_artifacts.save(active)
        await uow.publish_artifacts.save(deleted)
        await uow.commit()

    async with uow_factory() as uow:
        assert await uow.publish_artifacts.list_all() == (active,)
        assert await uow.publish_artifacts.list_all(include_deleted=True) == (active, deleted)
        selected = await uow.publish_artifacts.list_by_ids((deleted.id, active.id))
        assert set(selected) == {active, deleted}
