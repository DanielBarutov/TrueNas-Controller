"""Application use cases for station read models."""

from application.ports import StationListQuery, UnitOfWorkFactory
from domain.station import Station


class ListStationsUseCase(StationListQuery):
    """Load station state through a fresh UoW for each request."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, include_disabled: bool = False) -> list[Station]:
        async with self._uow_factory() as uow:
            return await uow.stations.list(include_disabled=include_disabled)
