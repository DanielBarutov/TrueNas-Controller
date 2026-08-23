from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from application.publish_commands import (
    CreatePublishJobUseCase,
    EnqueuePublishJobUseCase,
    PublishDraftValidationError,
    PublishIdempotencyConflictError,
    PublishJobNotFoundError,
    PublishTaskPayloadMismatchError,
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


@pytest.fixture
def uow_factory(engine: AsyncEngine) -> SqlAlchemyUnitOfWorkFactory:
    return SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))


def make_station(*, enabled: bool = True) -> Station:
    return Station(
        id=uuid4(),
        station_id=uuid4(),
        display_name="Client 01",
        hostname="client-01",
        role=StationRole.CLIENT,
        status=StationStatus.ONLINE if enabled else StationStatus.DISABLED,
        enabled=enabled,
    )


async def add_stations(
    factory: SqlAlchemyUnitOfWorkFactory,
    stations: tuple[Station, ...],
) -> None:
    async with factory() as uow:
        for station in stations:
            await uow.stations.add(station)
        await uow.commit()


async def test_create_publish_job_materializes_dynamic_selection_and_safe_defaults(
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    first, second = make_station(), make_station()
    await add_stations(uow_factory, (first, second))
    correlation_id = uuid4()

    draft = await CreatePublishJobUseCase(uow_factory).execute(
        label="build-001",
        game_name="game",
        station_ids=(first.station_id, second.station_id),
        idempotency_key="draft-key",
        correlation_id=correlation_id,
    )

    assert draft.job.dry_run is True
    assert draft.job.allow_hot_switch is False
    assert draft.job.status.value == "draft"
    assert [target.station_id for target in draft.targets] == [
        first.station_id,
        second.station_id,
    ]

    async with uow_factory() as uow:
        stored_targets = await uow.publish_targets.list_for_job(draft.job.id)
    assert {target.station_id for target in stored_targets} == {
        first.station_id,
        second.station_id,
    }


async def test_create_publish_job_rejects_unknown_disabled_and_duplicate_selection(
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    enabled = make_station()
    disabled = make_station(enabled=False)
    await add_stations(uow_factory, (enabled, disabled))
    use_case = CreatePublishJobUseCase(uow_factory)

    with pytest.raises(PublishDraftValidationError, match="station selection"):
        await use_case.execute(
            label="build",
            game_name="game",
            station_ids=(enabled.station_id, enabled.station_id),
            idempotency_key="duplicate-selection",
            correlation_id=uuid4(),
        )
    with pytest.raises(PublishDraftValidationError, match="station not found"):
        await use_case.execute(
            label="build",
            game_name="game",
            station_ids=(uuid4(),),
            idempotency_key="missing-station",
            correlation_id=uuid4(),
        )
    with pytest.raises(PublishDraftValidationError, match="station is disabled"):
        await use_case.execute(
            label="build",
            game_name="game",
            station_ids=(disabled.station_id,),
            idempotency_key="disabled-station",
            correlation_id=uuid4(),
        )


async def test_same_idempotency_request_returns_existing_draft_without_duplicates(
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    station = make_station()
    await add_stations(uow_factory, (station,))
    use_case = CreatePublishJobUseCase(uow_factory)
    values = {
        "label": "build",
        "game_name": "game",
        "station_ids": (station.station_id,),
        "idempotency_key": "same-request",
        "correlation_id": UUID(int=1),
    }

    first = await use_case.execute(**values)
    second = await use_case.execute(**values)

    assert second == first
    async with uow_factory() as uow:
        assert len(await uow.publish_targets.list_for_job(first.job.id)) == 1

    with pytest.raises(PublishIdempotencyConflictError, match="already used"):
        await use_case.execute(**{**values, "label": "another-build"})


class FakeQueue:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, UUID, str]] = []

    def enqueue(
        self,
        *,
        job_id: UUID,
        correlation_id: UUID,
        idempotency_key: str,
    ) -> None:
        self.calls.append((job_id, correlation_id, idempotency_key))


async def test_enqueue_reloads_job_and_sends_minimal_payload(
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    station = make_station()
    await add_stations(uow_factory, (station,))
    draft = await CreatePublishJobUseCase(uow_factory).execute(
        label="build",
        game_name="game",
        station_ids=(station.station_id,),
        idempotency_key="enqueue-key",
        correlation_id=UUID(int=2),
    )
    queue = FakeQueue()

    await EnqueuePublishJobUseCase(uow_factory, queue).execute(
        job_id=draft.job.id,
        correlation_id=draft.job.correlation_id,
        idempotency_key=draft.job.idempotency_key,
    )

    assert queue.calls == [(draft.job.id, draft.job.correlation_id, "enqueue-key")]

    with pytest.raises(PublishTaskPayloadMismatchError, match="correlation ID"):
        await EnqueuePublishJobUseCase(uow_factory, queue).execute(
            job_id=draft.job.id,
            correlation_id=UUID(int=3),
            idempotency_key=draft.job.idempotency_key,
        )
    assert len(queue.calls) == 1

    with pytest.raises(PublishJobNotFoundError, match="publish job not found"):
        await EnqueuePublishJobUseCase(uow_factory, queue).execute(
            job_id=uuid4(),
            correlation_id=uuid4(),
            idempotency_key="missing-job",
        )
