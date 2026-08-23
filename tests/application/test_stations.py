from uuid import uuid4

from application.stations import ListStationsUseCase
from domain.station import Station, StationRole, StationStatus


class FakeStationRepository:
    def __init__(self, stations: list[Station]) -> None:
        self._stations = stations
        self.requested_include_disabled: bool | None = None

    async def list(self, *, include_disabled: bool = False) -> list[Station]:
        self.requested_include_disabled = include_disabled
        return self._stations


class FakeUnitOfWork:
    def __init__(self, repository: FakeStationRepository) -> None:
        self.stations = repository

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
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
