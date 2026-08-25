"""Application use cases for station read models and operator edits."""

from dataclasses import replace
from uuid import UUID

from application.ports import StationListQuery, UnitOfWorkFactory
from domain.station import Station, StationRole, StationStatus


class StationNotFoundError(ValueError):
    """Raised when an operator updates a station that is not registered."""


class ListStationsUseCase(StationListQuery):
    """Load station state through a fresh UoW for each request."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, include_disabled: bool = False) -> list[Station]:
        async with self._uow_factory() as uow:
            return await uow.stations.list(include_disabled=include_disabled)


class UpdateStationUseCase:
    """Update editable station metadata while preserving its stable identity."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        *,
        station_id: UUID,
        display_name: str,
        hostname: str,
        role: StationRole,
        enabled: bool,
    ) -> Station:
        async with self._uow_factory() as uow:
            station = await uow.stations.get(station_id)
            if station is None or station.deleted_at is not None:
                raise StationNotFoundError("station not found")
            next_status = station.status
            if not enabled:
                next_status = StationStatus.DISABLED
            elif station.status is StationStatus.DISABLED:
                next_status = StationStatus.OFFLINE
            updated = replace(
                station,
                display_name=display_name,
                hostname=hostname,
                role=role,
                enabled=enabled,
                status=next_status,
            )
            result = await uow.stations.update_details(
                station_id,
                display_name=updated.display_name,
                hostname=updated.hostname,
                role=updated.role,
                enabled=updated.enabled,
            )
            if result is None:
                raise StationNotFoundError("station not found")
            await uow.commit()
            return result


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
