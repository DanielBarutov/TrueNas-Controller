"""Application query that loads current data and invokes the pure evaluator."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from application.ports import UnitOfWorkFactory
from domain.preflight import PreflightPolicy, PreflightReport, evaluate_preflight


class StationNotFoundError(LookupError):
    """Raised when preflight is requested for an unknown station."""


class EvaluateStationPreflightUseCase:
    """Evaluate a station from a fresh UoW read model."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        *,
        station_id: UUID,
        max_snapshot_age: timedelta = timedelta(seconds=30),
        required_drive_letter: str = "D:",
        min_free_bytes: int = 0,
        now: datetime | None = None,
    ) -> PreflightReport:
        evaluated_at = now or datetime.now(UTC)
        async with self._uow_factory() as uow:
            station = await uow.stations.get(station_id)
            if station is None:
                raise StationNotFoundError("station not found")
            snapshot = await uow.process_snapshots.latest(station_id)
            rules = await uow.process_rules.list_for_role(station.role)
        return evaluate_preflight(
            station,
            snapshot,
            rules,
            PreflightPolicy(
                max_snapshot_age=max_snapshot_age,
                required_drive_letter=required_drive_letter,
                min_free_bytes=min_free_bytes,
            ),
            now=evaluated_at,
        )
