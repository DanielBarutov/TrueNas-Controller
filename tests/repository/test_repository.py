from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

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


def make_station(**overrides: object) -> Station:
    values: dict[str, object] = {
        "id": uuid4(),
        "station_id": uuid4(),
        "display_name": "Client 01",
        "hostname": "client-01",
        "role": StationRole.CLIENT,
        "status": StationStatus.ONLINE,
    }
    values.update(overrides)
    return Station(**values)  # type: ignore[arg-type]


@pytest.fixture
def uow_factory(engine: AsyncEngine) -> SqlAlchemyUnitOfWorkFactory:
    return SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))


async def test_station_repository_round_trip(uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
    station = make_station()

    async with uow_factory() as uow:
        await uow.stations.add(station)
        await uow.commit()

    async with uow_factory() as uow:
        assert await uow.stations.get(station.station_id) == station


async def test_station_repository_updates_truenas_mapping(
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    station = make_station()
    async with uow_factory() as uow:
        await uow.stations.add(station)
        await uow.commit()

    async with uow_factory() as uow:
        updated = await uow.stations.update_storage_mapping(
            station.station_id,
            target_name="PC1",
            target_iqn="iqn.target.pc1",
            initiator_iqn="iqn.initiator.pc1",
        )
        await uow.commit()

    assert updated is not None
    assert updated.target_name == "PC1"
    assert updated.target_iqn == "iqn.target.pc1"
    assert updated.initiator_iqn == "iqn.initiator.pc1"


async def test_list_excludes_disabled_by_default(
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    enabled = make_station(display_name="Enabled")
    disabled = make_station(
        display_name="Disabled",
        enabled=False,
        status=StationStatus.DISABLED,
    )

    async with uow_factory() as uow:
        await uow.stations.add(enabled)
        await uow.stations.add(disabled)
        await uow.commit()

    async with uow_factory() as uow:
        assert await uow.stations.list() == [enabled]
        assert await uow.stations.list(include_disabled=True) == [disabled, enabled]


async def test_uow_rolls_back_when_context_exits_with_error(
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    station = make_station()

    with pytest.raises(RuntimeError, match="fail operation"):
        async with uow_factory() as uow:
            await uow.stations.add(station)
            raise RuntimeError("fail operation")

    async with uow_factory() as uow:
        assert await uow.stations.get(station.station_id) is None


async def test_station_id_is_unique(uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
    station = make_station()
    duplicate = make_station(station_id=station.station_id)

    async with uow_factory() as uow:
        await uow.stations.add(station)
        await uow.commit()

    with pytest.raises(IntegrityError):
        async with uow_factory() as uow:
            await uow.stations.add(duplicate)
            await uow.commit()


async def test_uow_factory_creates_independent_uows(
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    first = uow_factory()
    second = uow_factory()

    assert first is not second
    async with first, second:
        assert first._session is not second._session
