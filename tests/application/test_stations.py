from dataclasses import replace
from uuid import uuid4

from application.stations import (
    ListStationsUseCase,
    UpdateStationStorageMappingUseCase,
    UpdateStationUseCase,
)
from domain.station import Station, StationRole, StationStatus


class FakeStationRepository:
    def __init__(self, stations: list[Station]) -> None:
        self._stations = stations
        self.requested_include_disabled: bool | None = None

    async def list(self, *, include_disabled: bool = False) -> list[Station]:
        self.requested_include_disabled = include_disabled
        return self._stations

    async def get(self, station_id):
        return next(
            (station for station in self._stations if station.station_id == station_id),
            None,
        )

    async def update_details(self, station_id, *, display_name, hostname, role, enabled):
        station = await self.get(station_id)
        if station is None:
            return None
        updated = replace(
            station,
            display_name=display_name,
            hostname=hostname,
            role=role,
            enabled=enabled,
            status=StationStatus.DISABLED if not enabled else StationStatus.OFFLINE,
        )
        self._stations = [updated]
        return updated

    async def update_storage_mapping(self, station_id, *, target_name, target_iqn, initiator_iqn):
        station = await self.get(station_id)
        if station is None:
            return None
        updated = replace(
            station,
            target_name=target_name,
            target_iqn=target_iqn,
            initiator_iqn=initiator_iqn,
        )
        self._stations = [updated]
        return updated


class FakeUnitOfWork:
    def __init__(self, repository: FakeStationRepository) -> None:
        self.stations = repository

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    async def commit(self) -> None:
        return None


async def test_list_stations_use_case_passes_read_policy_to_repository() -> None:
    station = Station(
        id=uuid4(),
        station_id=uuid4(),
        display_name="Admin",
        hostname="admin-pc",
        role=StationRole.ADMIN,
        status=StationStatus.ONLINE,
    )
    repository = FakeStationRepository([station])
    use_case = ListStationsUseCase(lambda: FakeUnitOfWork(repository))

    result = await use_case.execute(include_disabled=True)

    assert result == [station]
    assert repository.requested_include_disabled is True


async def test_station_edit_preserves_uuid_and_updates_operator_fields() -> None:
    station = Station(
        id=uuid4(),
        station_id=uuid4(),
        display_name="Client",
        hostname="client-old",
        role=StationRole.CLIENT,
        status=StationStatus.ONLINE,
    )
    repository = FakeStationRepository([station])
    use_case = UpdateStationUseCase(lambda: FakeUnitOfWork(repository))

    updated = await use_case.execute(
        station_id=station.station_id,
        display_name="Client 01",
        hostname="client-new",
        role=StationRole.ADMIN,
        enabled=False,
    )

    assert updated.station_id == station.station_id
    assert updated.display_name == "Client 01"
    assert updated.hostname == "client-new"
    assert updated.role is StationRole.ADMIN
    assert updated.status is StationStatus.DISABLED


async def test_storage_mapping_edit_updates_only_mapping_fields() -> None:
    station = Station(
        id=uuid4(),
        station_id=uuid4(),
        display_name="Client",
        hostname="client",
        role=StationRole.CLIENT,
        status=StationStatus.ONLINE,
    )
    repository = FakeStationRepository([station])
    use_case = UpdateStationStorageMappingUseCase(lambda: FakeUnitOfWork(repository))

    updated = await use_case.execute(
        station_id=station.station_id,
        target_name="PC1",
        target_iqn="iqn.target",
        initiator_iqn="iqn.initiator",
    )

    assert updated.station_id == station.station_id
    assert updated.display_name == station.display_name
    assert updated.target_name == "PC1"
    assert updated.target_iqn == "iqn.target"
    assert updated.initiator_iqn == "iqn.initiator"
