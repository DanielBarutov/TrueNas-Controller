"""Application use cases for station read models and operator mapping edits."""

from uuid import UUID

from application.ports import StationListQuery, UnitOfWorkFactory
from domain.station import Station


class StationNotFoundError(ValueError):
    """Raised when an operator updates a station that is not registered."""


class ListStationsUseCase(StationListQuery):
    """Load station state through a fresh UoW for each request."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, include_disabled: bool = False) -> list[Station]:
        async with self._uow_factory() as uow:
            return await uow.stations.list(include_disabled=include_disabled)


class UpdateStationStorageMappingUseCase:
    """Persist the TrueNAS target metadata used by the publish worker."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        *,
        station_id: UUID,
        target_name: str | None,
        target_iqn: str | None,
        initiator_iqn: str | None,
    ) -> Station:
        async with self._uow_factory() as uow:
            station = await uow.stations.update_storage_mapping(
                station_id,
                target_name=target_name,
                target_iqn=target_iqn,
                initiator_iqn=initiator_iqn,
            )
            if station is None:
                raise StationNotFoundError("station not found")
            await uow.commit()
            return station
